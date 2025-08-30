DROP TABLE IF EXISTS classes CASCADE;
DROP TYPE IF EXISTS season;
DROP TYPE IF EXISTS first_or_second;
DROP TYPE IF EXISTS attribute;

CREATE TYPE season AS ENUM('spring', 'summer', 'fall');
CREATE TYPE first_or_second AS ENUM('first', 'second', 'third', 'fourth', 'mini-term');
CREATE TYPE attribute AS ENUM(
        'two-credit-writing', 
        'ah-foundations', 
        'chinese-student-requirements',
        'common-core',
        'language',
        'ns-foundations',
        'quantitative-reasoning',
        'ss-foundations',
        'signature-projects'
);

CREATE TABLE classes (
    class_id SERIAL PRIMARY KEY,
    course_code VARCHAR(20) NOT NULL,
    course_title TEXT,
    credit_hours NUMERIC(3,1),
    course_format TEXT,
    prerequisites TEXT,
    description TEXT,
    attributes attribute,
    learning_outcomes TEXT[],
    required_textbook TEXT,
    optional_textbooks TEXT[],
    academic_policies TEXT,
    instructor_email TEXT,
    instructor_name TEXT,
    office_location TEXT,
    office_hours TEXT,
    biography TEXT,
    year INT,
    semester season NOT NULL,
    semester_session first_or_second NOT NULL,
    schedule_days TEXT[],
    schedule_time_start TEXT,
    schedule_time_end TEXT,
    location TEXT,
    recitation_time TEXT,
    recitation_location TEXT,
    lab_time TEXT,
    lab_location TEXT,
    grading_policy TEXT,
    grade_scale TEXT,
    assignment_policy TEXT,
    communication_policy TEXT,
    teaching_methods TEXT
);
