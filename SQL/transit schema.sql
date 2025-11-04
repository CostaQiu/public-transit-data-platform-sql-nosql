-- MySQL Workbench Forward Engineering (updated)

SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

-- -----------------------------------------------------
-- Schema transit
-- -----------------------------------------------------
CREATE SCHEMA IF NOT EXISTS `transit` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci ;
USE `transit` ;

-- -----------------------------------------------------
-- Table `transit`.`calendar`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `transit`.`calendar` (
  `service_id` VARCHAR(64) NOT NULL,
  `monday` TINYINT(1) NOT NULL,
  `tuesday` TINYINT(1) NOT NULL,
  `wednesday` TINYINT(1) NOT NULL,
  `thursday` TINYINT(1) NOT NULL,
  `friday` TINYINT(1) NOT NULL,
  `saturday` TINYINT(1) NOT NULL,
  `sunday` TINYINT(1) NOT NULL,
  `start_date` DATE NOT NULL,
  `end_date` DATE NOT NULL,
  PRIMARY KEY (`service_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------
-- Table `transit`.`routes`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `transit`.`routes` (
  `route_id` VARCHAR(64) NOT NULL,
  `agency_id` VARCHAR(64) NULL DEFAULT NULL,
  `route_short_name` VARCHAR(64) NULL DEFAULT NULL,
  `route_long_name` VARCHAR(255) NULL DEFAULT NULL,
  `route_desc` VARCHAR(1024) NULL DEFAULT NULL,
  `route_type` SMALLINT NULL DEFAULT NULL,
  `route_color` VARCHAR(6) NULL DEFAULT NULL,
  PRIMARY KEY (`route_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------
-- Table `transit`.`trips`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `transit`.`trips` (
  `trip_id` VARCHAR(64) NOT NULL,
  `route_id` VARCHAR(64) NOT NULL,
  `service_id` VARCHAR(64) NOT NULL,
  `trip_headsign` VARCHAR(255) NULL DEFAULT NULL,
  `direction_id` SMALLINT NULL DEFAULT NULL,
  `shape_id` VARCHAR(64) NULL DEFAULT NULL,
  `wheelchair_accessible` SMALLINT NULL DEFAULT NULL,
  `bikes_allowed` SMALLINT NULL DEFAULT NULL,
  PRIMARY KEY (`trip_id`),
  INDEX `route_id` (`route_id` ASC) VISIBLE,
  INDEX `service_id` (`service_id` ASC) VISIBLE,
  CONSTRAINT `trips_ibfk_1` FOREIGN KEY (`route_id`) REFERENCES `transit`.`routes` (`route_id`),
  CONSTRAINT `trips_ibfk_2` FOREIGN KEY (`service_id`) REFERENCES `transit`.`calendar` (`service_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------
-- Table `transit`.`stops`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `transit`.`stops` (
  `stop_id` VARCHAR(64) NOT NULL,
  `stop_code` VARCHAR(64) NULL DEFAULT NULL,
  `stop_name` VARCHAR(255) NOT NULL,
  `stop_desc` VARCHAR(1024) NULL DEFAULT NULL,
  `stop_lat` FLOAT NOT NULL,
  `stop_lon` FLOAT NOT NULL,
  `zone_id` VARCHAR(64) NULL DEFAULT NULL,
  `wheelchair_boarding` SMALLINT NULL DEFAULT NULL,
  PRIMARY KEY (`stop_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------
-- Table `transit`.`stop_times`
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS `transit`.`stop_times` (
  `trip_id` VARCHAR(64) NOT NULL,
  `arrival_time` TIME NULL DEFAULT NULL,
  `departure_time` TIME NULL DEFAULT NULL,
  `stop_id` VARCHAR(64) NOT NULL,
  `stop_sequence` INT NOT NULL,
  `stop_headsign` VARCHAR(255) NULL DEFAULT NULL,
  `pickup_type` SMALLINT NULL DEFAULT NULL,
  `drop_off_type` SMALLINT NULL DEFAULT NULL,
  `shape_dist_traveled` FLOAT NULL DEFAULT NULL,
  PRIMARY KEY (`trip_id`, `stop_sequence`),
  INDEX `idx_stop_times_stop_id` (`stop_id` ASC) VISIBLE,
  CONSTRAINT `stop_times_ibfk_1` FOREIGN KEY (`trip_id`) REFERENCES `transit`.`trips` (`trip_id`),
  CONSTRAINT `stop_times_ibfk_2` FOREIGN KEY (`stop_id`) REFERENCES `transit`.`stops` (`stop_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET SQL_MODE=@OLD_SQL_MODE;
SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS;
