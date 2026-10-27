CREATE DATABASE IF NOT EXISTS weatherhub_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE weatherhub_db;

CREATE TABLE IF NOT EXISTS favorites (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    city VARCHAR(120) NOT NULL,
    country CHAR(2) NOT NULL,
    nickname VARCHAR(80) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    CONSTRAINT uq_favorites_city_country UNIQUE (city, country)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
