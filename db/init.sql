-- room table
CREATE TABLE room (
    name VARCHAR(32) PRIMARY KEY,
    creator VARCHAR(32) NOT NULL,
    date_created TIMESTAMP(0) WITH TIME ZONE NOT NULL DEFAULT NOW(),
    is_deletable BOOLEAN NOT NULL DEFAULT TRUE
);

-- message table
CREATE TABLE message (
    id BIGSERIAL PRIMARY KEY,
    message VARCHAR(255) NOT NULL,
    author VARCHAR(32) NOT NULL,
    date_posted TIMESTAMP(0) WITH TIME ZONE NOT NULL DEFAULT NOW(),
    room VARCHAR(32) NOT NULL REFERENCES room(name)
);

-- create QGIS and QField undeletable rooms
INSERT INTO room (name, creator, is_deletable)
VALUES
    ('QGIS', 'Geotribu', false),
    ('QField', 'Geotribu', false);
