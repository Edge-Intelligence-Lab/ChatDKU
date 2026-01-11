CREATE TABLE dku_class_schedule (
    id SERIAL PRIMARY KEY,

    term VARCHAR(10),          -- 去掉 NOT NULL
    session VARCHAR(10),

    subject VARCHAR(50),
    catalog VARCHAR(20),
    section VARCHAR(10),

    instructor_name VARCHAR(100),
    course_title TEXT,

    facility_id VARCHAR(100),

    meeting_start TIME,        -- 允许空
    meeting_end TIME,

    days TEXT[],               -- 允许空数组

    max_units NUMERIC(4,2),
    class_type VARCHAR(20),

    instructor_email VARCHAR(200),
    preferred BOOLEAN DEFAULT FALSE
);