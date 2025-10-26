-- Create database
CREATE DATABASE IF NOT EXISTS game_portal CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE game_portal;

-- Users
CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Games master
CREATE TABLE IF NOT EXISTS games (
  id INT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(50) NOT NULL UNIQUE,
  name VARCHAR(100) NOT NULL,
  description TEXT
) ENGINE=InnoDB;

-- A play session per user per game
CREATE TABLE IF NOT EXISTS plays (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  game_id INT NOT NULL,
  status ENUM('active','completed','abandoned') DEFAULT 'active',
  started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME NULL,
  total_score INT DEFAULT 0,
  CONSTRAINT fk_plays_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  CONSTRAINT fk_plays_game FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
  INDEX (user_id), INDEX (game_id)
) ENGINE=InnoDB;

-- Per-level record for each play
CREATE TABLE IF NOT EXISTS play_levels (
  id INT AUTO_INCREMENT PRIMARY KEY,
  play_id INT NOT NULL,
  level ENUM('low','medium','high') NOT NULL,
  score INT DEFAULT 0,
  duration_seconds INT DEFAULT 0,
  started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME NULL,
  UNIQUE KEY uniq_play_level (play_id, level),
  CONSTRAINT fk_pl_play FOREIGN KEY (play_id) REFERENCES plays(id) ON DELETE CASCADE,
  INDEX (play_id)
) ENGINE=InnoDB;

-- Seed games
INSERT INTO games (code, name, description) VALUES
  ('emoji', 'Emoji Quest', 'Guess the word from emojis!'),
  ('math',  'Math Sprint', 'Quick mental math challenge!')
ON DUPLICATE KEY UPDATE name=VALUES(name), description=VALUES(description);
