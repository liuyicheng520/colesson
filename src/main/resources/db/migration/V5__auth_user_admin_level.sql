ALTER TABLE auth_users
    ADD COLUMN admin_level VARCHAR(32) NOT NULL DEFAULT '' AFTER password_algo;

UPDATE auth_users SET admin_level = 'super' WHERE username = 'lyc';
UPDATE auth_users SET admin_level = 'ops' WHERE username = 'ops_demo';
