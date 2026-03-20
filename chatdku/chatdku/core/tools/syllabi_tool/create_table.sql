-- DROP TABLE IF EXISTS curriculum CASCADE;
-- DROP TYPE IF EXISTS season;
-- DROP TYPE IF EXISTS first_or_second;
-- DROP TYPE IF EXISTS attribute;

-- CREATE TYPE season AS ENUM('spring', 'summer', 'fall');
-- CREATE TYPE first_or_second AS ENUM('first', 'second', 'third', 'fourth', 'mini-term');

CREATE TABLE curriculum (
    class_id SERIAL PRIMARY KEY,
    course_code VARCHAR(20) NOT NULL,
    course_title TEXT,
    credit_hours NUMERIC(3,1),
    course_format TEXT,
    prerequisites TEXT,
    description TEXT,
    attributes TEXT[],
    -- Maybe we can create instructors table
    instructor_email TEXT,
    instructor_name TEXT,
    office_location TEXT,
    office_hours TEXT,
    instructor_biography TEXT,
    learning_outcomes TEXT[],
    required_textbook TEXT,
    optional_textbooks TEXT[],
    academic_policies TEXT,
    year INT,
    semester season NOT NULL,
    semester_session first_or_second NOT NULL,
    lecture_days VARCHAR(32)[],
    lecture_time_start VARCHAR(32),
    lecture_time_end VARCHAR(32),
    lecture_location VARCHAR(32),
    recitation_day VARCHAR(32),
    recitation_time_start VARCHAR(32),
    recitation_time_end VARCHAR(32),
    recitation_location VARCHAR(32),
    lab_day VARCHAR(32),
    lab_time_start VARCHAR(32),
    lab_time_end VARCHAR(32),
    lab_location VARCHAR(32),
    grading_policy TEXT,
    grade_scale TEXT,
    assignment_policy TEXT,
    communication_policy TEXT,
    teaching_methods TEXT,
    late_submission_policy TEXT
);
