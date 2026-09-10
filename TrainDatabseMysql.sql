CREATE DATABASE train;

USE train;

-- DROP EVENT ticket_reset;

SET GLOBAL event_scheduler = OFF;
SET GLOBAL event_scheduler = ON;
CREATE EVENT ticket_reset
  ON SCHEDULE
    EVERY 1 DAY
    STARTS "2024-11-11 00:00:00"
  DO
    UPDATE train_availability
    SET available_ac_seats = (
		CASE 
			WHEN train_number IN (12951, 12952) AND day_of_week = DAYNAME(CURRENT_DATE - INTERVAL 1 DAY) THEN 100
			WHEN train_number IN (12009, 12010) AND day_of_week = DAYNAME(CURRENT_DATE - INTERVAL 1 DAY) THEN 100
			WHEN train_number IN (12274, 12275) AND day_of_week = DAYNAME(CURRENT_DATE - INTERVAL 1 DAY) THEN 100
			WHEN train_number IN (12611, 12612) AND day_of_week = DAYNAME(CURRENT_DATE - INTERVAL 1 DAY) THEN 150
			ELSE 120
		END),
        available_gen_seats = (
        CASE 
			WHEN train_number IN (12951, 12952) AND day_of_week = DAYNAME(CURRENT_DATE - INTERVAL 1 DAY) THEN 100
			WHEN train_number IN (12009, 12010) AND day_of_week = DAYNAME(CURRENT_DATE - INTERVAL 1 DAY) THEN 120
			WHEN train_number IN (12274, 12275) AND day_of_week = DAYNAME(CURRENT_DATE - INTERVAL 1 DAY) THEN 150
			WHEN train_number IN (12611, 12612) AND day_of_week = DAYNAME(CURRENT_DATE - INTERVAL 1 DAY) THEN 130
			ELSE 150
		END);

DELIMITER $$

CREATE TRIGGER before_register_email_check
BEFORE INSERT ON Login
FOR EACH ROW
BEGIN
    DECLARE email_exists INT;
    
    -- Check if email already exists in the table
    SELECT COUNT(*) INTO email_exists
    FROM Login
    WHERE Email = NEW.Email;

    IF email_exists > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Email already registered';
    END IF;
END $$

DELIMITER ;

DELIMITER $$

CREATE TRIGGER after_user_login_logout
AFTER UPDATE ON Login
FOR EACH ROW
BEGIN
    -- Check if the user has logged in (status change to 'active')
    IF OLD.User_Status = 'inactive' AND NEW.User_Status = 'active' THEN
        -- Set the last login time when the user logs in
        UPDATE Login_Time
        SET Last_Login_Time = NOW()
        WHERE UserId = NEW.UserId;
    END IF;

    -- Check if the user has logged out (status change to 'inactive')
    IF OLD.User_Status = 'active' AND NEW.User_Status = 'inactive' THEN
        -- Optionally update the last login time when user logs out
        UPDATE Login_Time
        SET Last_Login_Time = NOW()
        WHERE UserId = NEW.UserId;
    END IF;
END $$

DELIMITER ;

DELIMITER $$

CREATE TRIGGER after_user_register
AFTER INSERT ON Login
FOR EACH ROW
BEGIN
    INSERT INTO User_Registration_Log (UserId, Email, Registration_Time)
    VALUES (NEW.UserId, NEW.Email, NOW());
    INSERT INTO Login_Time (UserId)
    VALUES (NEW.UserId);
END $$

DELIMITER ;

SHOW PROCESSLIST;
SHOW EVENTS;

-- Login Table
CREATE TABLE IF NOT EXISTS Login (
	UserId VARCHAR(20),
    Pwd VARCHAR(20),
    Mobile_No BIGINT CHECK (CHAR_LENGTH(Mobile_No) = 10 AND Mobile_No REGEXP '^[0-9]{10}$'),
    Email VARCHAR(30) UNIQUE NOT NULL,
    User_Status VARCHAR(20) DEFAULT 'inactive',
    PRIMARY KEY (UserId)
);

-- Login Time table
CREATE TABLE IF NOT EXISTS Login_Time (
	UserId VARCHAR(20) PRIMARY KEY,
    Last_Login_Time TIMESTAMP,
    FOREIGN KEY (UserId) REFERENCES Login(UserId) ON DELETE CASCADE
);

-- User Log Table
CREATE TABLE User_Registration_Log (
    Log_Id INT AUTO_INCREMENT PRIMARY KEY,
    UserId VARCHAR(255),
    Email VARCHAR(255),
    Registration_Time TIMESTAMP,
    FOREIGN KEY (UserId) REFERENCES Login(UserId) ON DELETE CASCADE
);

-- Passengers Table
CREATE TABLE IF NOT EXISTS passengers (
    passenger_name VARCHAR(255),
    age INT,
    mobile_no BIGINT,
    adhaar_number BIGINT,
    sex VARCHAR(10),
    PRIMARY KEY (adhaar_number)
);

-- Trains Table
CREATE TABLE IF NOT EXISTS trains (
    train_name VARCHAR(255),
    src VARCHAR(255),
    destination VARCHAR(255),
    no_of_stops INT,
    train_number BIGINT,
    price_per_ticket INT,
    PRIMARY KEY (train_number)
);

-- Tickets Table
CREATE TABLE IF NOT EXISTS tickets (
    ticket_type VARCHAR(20),
    confirmation_status VARCHAR(20),
    departure_date DATE,
    arrival_date DATE,
    departure_time TIME,
    arrival_time TIME,
    ticket_source VARCHAR(20),
    ticket_destination VARCHAR(20),
    ticket_ID BIGINT PRIMARY KEY,
    ticket_cluster BIGINT,
    amount BIGINT,
    coach_no VARCHAR(10),
    berth_no INT
);

-- Stations Table with linear order
CREATE TABLE IF NOT EXISTS stations (
    station_name VARCHAR(255),
    departure_time TIME,
    city VARCHAR(255),
    station_code VARCHAR(25),
    no_of_platforms INT,
    arrival_time TIME,
    order_in_route INT,
    PRIMARY KEY (station_code)
);

-- MyTickets Table
CREATE TABLE IF NOT EXISTS MyTickets (
	UserId VARCHAR(20),
    ticket_ID BIGINT,
    FOREIGN KEY (UserId) REFERENCES Login(UserId) ON DELETE CASCADE,
    FOREIGN KEY (ticket_ID) REFERENCES tickets(ticket_ID) ON DELETE CASCADE,
    PRIMARY KEY (ticket_ID)
);

-- Booking Table
CREATE TABLE booking (
    adhaar_number BIGINT,
    ticket_ID BIGINT,
    FOREIGN KEY (adhaar_number) REFERENCES passengers(adhaar_number) ON DELETE CASCADE,
    FOREIGN KEY (ticket_ID) REFERENCES tickets(ticket_ID) ON DELETE CASCADE,
    PRIMARY KEY (adhaar_number, ticket_ID)
);

-- Reservation Table
CREATE TABLE reservation (
    ticket_ID BIGINT,
    train_number BIGINT,
    FOREIGN KEY (ticket_ID) REFERENCES tickets(ticket_ID) ON DELETE CASCADE,
    FOREIGN KEY (train_number) REFERENCES trains(train_number) ON DELETE CASCADE,
    PRIMARY KEY (ticket_ID)
);

-- Stops_at Table
CREATE TABLE IF NOT EXISTS stops_at (
    train_number BIGINT,
    station_code VARCHAR(25),
    order_in_route INT,
    PRIMARY KEY (train_number, station_code),
    FOREIGN KEY (train_number) REFERENCES trains(train_number) ON DELETE CASCADE,
    FOREIGN KEY (station_code) REFERENCES stations(station_code) ON DELETE CASCADE
);

-- Train Availability Table
CREATE TABLE IF NOT EXISTS train_availability (
    train_number BIGINT,
    day_of_week ENUM('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'),
    available_ac_seats INT,
    available_gen_seats INT,
    version_number INT DEFAULT 0,
    PRIMARY KEY (train_number, day_of_week),
    FOREIGN KEY (train_number) REFERENCES trains(train_number) ON DELETE CASCADE
);

-- Train Seats Table
CREATE TABLE IF NOT EXISTS train_seats (
    train_number BIGINT,
    ac_seats INT,
    gen_seats INT,
    PRIMARY KEY (train_number),
    FOREIGN KEY (train_number) REFERENCES trains(train_number) ON DELETE CASCADE
);

-- Insert Station Data with Linear Order
INSERT INTO stations (station_name, departure_time, city, station_code, no_of_platforms, arrival_time, order_in_route)
VALUES 
('Mumbai Central', '08:00:00', 'Mumbai', 'BCT', 5, '07:45:00', 1),
('New Delhi', '12:00:00', 'New Delhi', 'NDLS', 16, '11:45:00', 2),
('Howrah Junction', '14:00:00', 'Kolkata', 'HWH', 23, '13:45:00', 3),
('Chennai Central', '06:30:00', 'Chennai', 'MAS', 17, '06:00:00', 4),
('Bengaluru City', '09:15:00', 'Bengaluru', 'SBC', 10, '08:45:00', 5);

-- Insert Trains Data
INSERT INTO trains (train_name, src, destination, no_of_stops, train_number, price_per_ticket)
VALUES 
('Rajdhani Express', 'Mumbai Central', 'New Delhi', 1, 12951, 1500),
('Rajdhani Express Return', 'New Delhi', 'Mumbai Central', 1, 12952, 1500),
('Shatabdi Express', 'Mumbai Central', 'Howrah Junction', 2, 12009, 1300),
('Shatabdi Express Return', 'Howrah Junction', 'Mumbai Central', 2, 12010, 1300),
('Duronto Express', 'New Delhi', 'Chennai Central', 3, 12274, 1400),
('Duronto Express Return', 'Chennai Central', 'New Delhi', 3, 12275, 1400),
('Garib Rath Express', 'Howrah Junction', 'Bengaluru City', 4, 12611, 1200),
('Garib Rath Express Return', 'Bengaluru City', 'Howrah Junction', 4, 12612, 1200),
('Karnataka Express', 'Mumbai Central', 'Bengaluru City', 5, 12627, 1600),
('Karnataka Express Return', 'Bengaluru City', 'Mumbai Central', 5, 12628, 1600);

-- Insert Available Seats Data
INSERT INTO train_availability (train_number, day_of_week, available_ac_seats, available_gen_seats, version_number)
SELECT train_number, day, 
    CASE 
        WHEN train_number IN (12951, 12952) THEN 1
        WHEN train_number IN (12009, 12010) THEN 100
        WHEN train_number IN (12274, 12275) THEN 100
        WHEN train_number IN (12611, 12612) THEN 150
        ELSE 120
    END AS available_ac_seats,
    CASE 
        WHEN train_number IN (12951, 12952) THEN 100
        WHEN train_number IN (12009, 12010) THEN 120
        WHEN train_number IN (12274, 12275) THEN 150
        WHEN train_number IN (12611, 12612) THEN 130
        ELSE 150
    END AS available_gen_seats,
    1 AS version_number
FROM trains, 
     (SELECT 'Monday' AS day UNION ALL SELECT 'Tuesday' UNION ALL SELECT 'Wednesday' 
      UNION ALL SELECT 'Thursday' UNION ALL SELECT 'Friday' UNION ALL SELECT 'Saturday' UNION ALL SELECT 'Sunday') days;

-- Insert Total Seats Data 
INSERT INTO train_seats (train_number, ac_seats, gen_seats)
SELECT train_number, 
    CASE 
        WHEN train_number IN (12951, 12952) THEN 1
        WHEN train_number IN (12009, 12010) THEN 100
        WHEN train_number IN (12274, 12275) THEN 100
        WHEN train_number IN (12611, 12612) THEN 150
        ELSE 120
    END AS ac_seats,
    CASE 
        WHEN train_number IN (12951, 12952) THEN 100
        WHEN train_number IN (12009, 12010) THEN 120
        WHEN train_number IN (12274, 12275) THEN 150
        WHEN train_number IN (12611, 12612) THEN 130
        ELSE 150
    END AS gen_seats
FROM trains;

-- Insert Stops Data 
INSERT INTO stops_at (train_number, station_code, order_in_route) VALUES
(12951, 'BCT', 1),
(12951, 'NDLS', 2),
(12009, 'BCT', 1),
(12009, 'HWH', 2),
(12274, 'NDLS', 1),
(12274, 'MAS', 2),
(12611, 'HWH', 1),
(12611, 'SBC', 2),
(12627, 'BCT', 1),
(12627, 'SBC', 2);

-- SET SQL_SAFE_UPDATES = 0;
-- DELETE FROM Login;
-- DELETE FROM booking;
-- DELETE FROM reservation;
-- DELETE FROM MyTickets;
-- DELETE FROM tickets;
-- DELETE FROM passengers;
-- DELETE FROM Login_Time;
-- DELETE FROM User_Registration_Log;


select * from trains;
select * from passengers;
select * from tickets;
select * from train_availability;
select * from train_seats;
select * from booking;
select * from reservation;
select * from MyTickets;
select * from Login;
select * from stops_at;
select * from Login_Time;
select * from User_Registration_Log;

-- drop table train_availability;
-- drop table reservation;
-- drop table booking;
-- drop table MyTickets;
-- drop table stops_at;
-- drop table trains;
-- drop table stations;
-- drop table passengers;
-- drop table booking;
-- drop table tickets;
-- drop table Login;
-- drop table Login_Time;
-- drop table User_Registration_Log;

-- drop database train;