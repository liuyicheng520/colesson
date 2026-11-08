"""Tutor web search — 多源并行检索 + LLM 智能兜底（避免境外 API 不可达导致假超时）。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import TYPE_CHECKING

import httpx

from app.core.config import get_settings
from app.schemas.tutor import WebSearchSource
from app.utils.async_timeout import async_timeout

if TYPE_CHECKING:
    from app.llm.gateway import LLMGateway

logger = logging.getLogger(__name__)

_LLM_SEARCH_SYSTEM = (
    "你是联网检索助手。根据用户问题整理可用于辅导的权威知识点摘要。"
    "输出严格 JSON（不要 markdown 代码块）："
    '{"summary":"200-600字中文摘要","sources":[{"title":"来源或主题名","snippet":"一句话要点"}]}'
    "要求：事实准确、条理清晰，sources 至少 2 条。"
)


class TutorWebSearchService:
    PROVIDER_TIMEOUT_SEC = 3.0
    TOTAL_BUDGET_SEC = 6.0
    LLM_FALLBACK_TIMEOUT_SEC = 12.0
    MAX_CONTEXT_CHARS = 1500

    DDG_INSTANT_URL = "https://api.duckduckgo.com/"
    SERPER_URL = "https://google.serper.dev/search"

    def __init__(self, llm: LLMGateway | None = None) -> None:
        self.llm = llm
        self.settings = get_settings()

    def _proxy(self) -> str | None:
        explicit = (getattr(self.settings, "web_search_proxy", None) or "").strip()
        if explicit:
            return explicit
        return None

    def _client(self) -> httpx.AsyncClient:
        proxy = self._proxy()
        return httpx.AsyncClient(
            timeout=self.PROVIDER_TIMEOUT_SEC,
            trust_env=True,
            proxy=proxy,
            headers={"User-Agent": "EduNexus-Tutor/1.0"},
            follow_redirects=True,
        )

    @staticmethod
    def _merge(
        parts: list[tuple[str, list[WebSearchSource], bool]],
        max_sources: int,
    ) -> tuple[str, list[WebSearchSource], bool]:
        context_parts: list[str] = []
        sources: list[WebSearchSource] = []
        any_timed_out = False
        seen_snippets: set[str] = set()

        for summary, srcs, timed_out in parts:
            any_timed_out = any_timed_out or timed_out
            if summary and summary not in context_parts:
                context_parts.append(summary)
            for s in srcs:
                key = (s.title or "") + (s.snippet or "")
                if key in seen_snippets:
                    continue
                seen_snippets.add(key)
                sources.append(s)

        summary_text = "\n".join(context_parts)[: TutorWebSearchService.MAX_CONTEXT_CHARS]
        return summary_text, sources[:max_sources], any_timed_out and not summary_text and not sources

    async def _fetch_wikipedia(
        self, query: str, lang: str, max_sources: int
    ) -> tuple[str, list[WebSearchSource], bool]:
        sources: list[WebSearchSource] = []
        context_parts: list[str] = []
        timed_out = False
        api = f"https://{lang}.wikipedia.org/w/api.php"

        try:
            async with self._client() as client:
                search_resp = await client.get(
                    api,
                    params={
                        "action": "query",
                        "list": "search",
                        "srsearch": query,
                        "format": "json",
                        "utf8": 1,
                        "srlimit": min(3, max_sources),
                    },
                )
                if search_resp.status_code != 200:
                    return "", [], False
                hits = (search_resp.json().get("query") or {}).get("search") or []
                if not hits:
                    return "", [], False

                page_ids = [str(h["pageid"]) for h in hits[:max_sources] if h.get("pageid")]
                if not page_ids:
                    return "", [], False

                extract_resp = await client.get(
                    api,
                    params={
                        "action": "query",
                        "pageids": "|".join(page_ids),
                        "prop": "extracts|info",
                        "exintro": 1,
                        "explaintext": 1,
                        "inprop": "url",
                        "format": "json",
                    },
                )
                if extract_resp.status_code != 200:
                    return "", [], False

                pages = (extract_resp.json().get("query") or {}).get("pages") or {}
                for page in pages.values():
                    title = (page.get("title") or "").strip()
                    extract = (page.get("extract") or "").strip()
                    url = (page.get("fullurl") or "").strip()
                    if not extract:
                        continue
                    snippet = extract[:280]
                    context_parts.append(snippet)
                    sources.append(
                        WebSearchSource(
                            title=f"维基百科 · {title}" if title else "维基百科",
                            url=url,
                            snippet=snippet[:160],
                        )
                    )
        except httpx.TimeoutException:
            timed_out = True
            logger.debug("Wikipedia (%s) timeout query=%s", lang, query[:60])
        except Exception as exc:
            logger.debug("Wikipedia (%s) failed: %s", lang, exc)

        summary = "\n".join(context_parts)[: self.MAX_CONTEXT_CHARS]
        return summary, sources[:max_sources], timed_out

    async def _fetch_ddg(self, query: str, max_sources: int) -> tuple[str, list[WebSearchSource], bool]:
        sources: list[WebSearchSource] = []
        context_parts: list[str] = []
        timed_out = False

        try:
            async with self._client() as client:
                resp = await client.get(
                    self.DDG_INSTANT_URL,
                    params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
                )
                if resp.status_code != 200:
                    return "", [], False
                data = resp.json()
                abstract = (data.get("AbstractText") or "").strip()
                abstract_url = (data.get("AbstractURL") or "").strip()
                if abstract:
                    context_parts.append(abstract[:400])
                    if abstract_url:
                        sources.append(
                            WebSearchSource(
                                title=data.get("Heading") or query,
                                url=abstract_url,
                                snippet=abstract[:200],
                            )
                        )
                for item in (data.get("RelatedTopics") or [])[:max_sources]:
                    if isinstance(item, dict) and "Text" in item:
                        text = str(item["Text"])[:300]
                        url = item.get("FirstURL") or ""
                        context_parts.append(text)
                        if url:
                            sources.append(
                                WebSearchSource(title=text[:60], url=url, snippet=text[:160])
                            )
        except httpx.TimeoutException:
            timed_out = True
            logger.debug("DDG timeout query=%s", query[:60])
        except Exception as exc:
            logger.debug("DDG failed: %s", exc)

        summary = "\n".join(context_parts)[: self.MAX_CONTEXT_CHARS]
        return summary, sources[:max_sources], timed_out

    async def _fetch_serper(self, query: str, max_sources: int) -> tuple[str, list[WebSearchSource], bool]:
        api_key = (getattr(self.settings, "serper_api_key", None) or "").strip()
        if not api_key:
            return "", [], False

        sources: list[WebSearchSource] = []
        context_parts: list[str] = []
        timed_out = False

        try:
            async with self._client() as client:
                resp = await client.post(
                    self.SERPER_URL,
                    json={"q": query, "num": max_sources, "gl": "cn", "hl": "zh-cn"},
                    headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                )
                if resp.status_code != 200:
                    return "", [], False
                data = resp.json()
                for item in (data.get("organic") or [])[:max_sources]:
                    title = (item.get("title") or "").strip()
                    snippet = (item.get("snippet") or "").strip()
                    url = (item.get("link") or "").strip()
                    if not snippet:
                        continue
                    context_parts.append(snippet[:300])
                    sources.append(
                        WebSearchSource(title=title or query, url=url, snippet=snippet[:160])
                    )
        except httpx.TimeoutException:
            timed_out = True
            logger.debug("Serper timeout query=%s", query[:60])
        except Exception as exc:
            logger.debug("Serper failed: %s", exc)

        summary = "\n".join(context_parts)[: self.MAX_CONTEXT_CHARS]
        return summary, sources[:max_sources], timed_out

    async def _llm_fallback(
        self,
        query: str,
        max_sources: int,
        user_id: int | None,
        task_id: int | None,
    ) -> tuple[str, list[WebSearchSource], bool]:
        if not self.llm:
            return "", [], False

        messages = [
            {"role": "system", "content": _LLM_SEARCH_SYSTEM},
            {"role": "user", "content": query},
        ]
        try:
            async with async_timeout(self.LLM_FALLBACK_TIMEOUT_SEC):
                result = await self.llm.chat(
                    messages,
                    temperature=0.25,
                    max_tokens=700,
                    user_id=user_id,
                    task_id=task_id,
                    skip_security=True,
                )
        except TimeoutError:
            logger.warning("LLM search fallback timeout query=%s", query[:60])
            return "", [], False
        except Exception as exc:
            logger.warning("LLM search fallback failed: %s", exc)
            return "", [], False

        raw = (result.content or "").strip()
        if not raw:
            return "", [], False

        payload: dict | None = None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                try:
                    payload = json.loads(match.group(0))
                except json.JSONDecodeError:
                    payload = None

        if not payload:
            summary = raw[: self.MAX_CONTEXT_CHARS]
            sources = [
                WebSearchSource(
                    title="智能检索摘要",
                    url="",
                    snippet=summary[:160],
                )
            ]
            return summary, sources[:max_sources], True

        summary = str(payload.get("summary") or "").strip()[: self.MAX_CONTEXT_CHARS]
        sources: list[WebSearchSource] = []
        for item in (payload.get("sources") or [])[:max_sources]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "智能检索").strip()
            snippet = str(item.get("snippet") or "").strip()
            if title or snippet:
                sources.append(
                    WebSearchSource(
                        title=title or "智能检索",
                        url="",
                        snippet=snippet[:160],
                    )
                )

        if not summary and sources:
            summary = "\n".join(s.snippet for s in sources if s.snippet)[: self.MAX_CONTEXT_CHARS]

        if not summary and not sources:
            return "", [], False

        logger.info("LLM search fallback ok query=%s sources=%d", query[:60], len(sources))
        return summary, sources[:max_sources], True

    async def _fetch_http_providers(self, query: str, max_sources: int) -> tuple[str, list[WebSearchSource], bool]:
        tasks = [
            self._fetch_wikipedia(query, "zh", max_sources),
            self._fetch_wikipedia(query, "en", max_sources),
            self._fetch_ddg(query, max_sources),
            self._fetch_serper(query, max_sources),
        ]
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.TOTAL_BUDGET_SEC,
            )
        except asyncio.TimeoutError:
            logger.warning("HTTP web search budget exceeded query=%s", query[:60])
            return "", [], True

        parts: list[tuple[str, list[WebSearchSource], bool]] = []
        for item in results:
            if isinstance(item, Exception):
                logger.debug("HTTP provider error: %s", item)
                continue
            parts.append(item)

        return self._merge(parts, max_sources)

    async def search(
        self,
        query: str,
        max_sources: int = 5,
        *,
        user_id: int | None = None,
        task_id: int | None = None,
    ) -> tuple[str, list[WebSearchSource], bool]:
        q = (query or "").strip()
        if not q:
            return "", [], False

        summary, sources, http_timed_out = await self._fetch_http_providers(q, max_sources)
        if summary or sources:
            return summary, sources, False

        llm_summary, llm_sources, llm_ok = await self._llm_fallback(q, max_sources, user_id, task_id)
        if llm_ok and (llm_summary or llm_sources):
            return llm_summary, llm_sources, False

        return "", [], http_timed_out or not llm_ok
