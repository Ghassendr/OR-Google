-- Migration script for Exam Management System V2
-- This script adds tables for salle management and distribution history

-- 1. Classrooms table
CREATE TABLE IF NOT EXISTS `salle` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(50) NOT NULL UNIQUE,
    `capacity` INT NOT NULL,
    `building` VARCHAR(10) NOT NULL,
    `sous_cap1` INT,
    `sous_cap2` INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. Distribution History table
-- Stores snapshots of algorithm runs
CREATE TABLE IF NOT EXISTS `distribution_history` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(200),
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `data_json` LONGTEXT NOT NULL,
    `params_json` TEXT,
    `is_active` TINYINT(1) DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. Optimization: Clear old salle table if exists (optional, depends on migration strategy)
-- For now we just ensure tables exist.
