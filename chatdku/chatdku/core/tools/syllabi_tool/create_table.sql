DROP TABLE IF EXISTS classes CASCADE;
DROP TYPE IF EXISTS season;
DROP TYPE IF EXISTS first_or_second;
DROP TYPE IF EXISTS attribute;

CREATE TYPE season AS ENUM('spring', 'summer', 'fall');
CREATE TYPE first_or_second AS ENUM('first', 'second', 'third', 'fourth', 'mini-term');

CREATE TABLE curriculum (
    class_id SERIAL PRIMARY KEY,
    course_code VARCHAR(20) NOT NULL,
    course_title VARCHAR(255),
    credit_hours NUMERIC(3,1),
    course_format VARCHAR(128),
    prerequisites VARCHAR(255),
    -- This can be left as a TEXT
    description TEXT,
    attributes attribute,
    -- Maybe we can create instructors table
    instructor_email VARCHAR(255),
    instructor_name VARCHAR(255)[],
    office_location VARCHAR(32),
    office_hours VARCHAR(255),
    -- This can be left as a TEXT
    instructor_biography TEXT,
    learning_outcomes TEXT[],
    required_textbook VARCHAR(255),
    optional_textbooks VARCHAR(255)[],
    academic_policies TEXT,
    year INT,
    semester season NOT NULL,
    semester_session first_or_second NOT NULL,
    lecture_days VARCHAR(64),
    lecture_time_start VARCHAR(32),
    lecture_time_end VARCHAR(32),
    location VARCHAR(32),
    recitation_day VARCHAR(32),
    recitation_time VARCHAR(32),
    recitation_location VARCHAR(32),
    lab_day VARCHAR(32),
    lab_time VARCHAR(32),
    lab_location VARCHAR(32),
    grading_policy TEXT,
    grade_scale VARCHAR(255),
    assignment_policy TEXT,
    communication_policy TEXT,
    teaching_methods TEXT,
    late_submission_policy TEXT,
);
