import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def fetch_course_schedule_schema(conn):
    """
    Fetch schema with enhanced descriptions for time and day columns.
    """
    # 先获取实际的列名
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'dku_class_schedule'
            ORDER BY ordinal_position;
        """)
        columns = cur.fetchall()
    
    # 手动构建 schema（基于你的数据结构）
    schema_desc = """TABLE: dku_class_schedule
        DATABASE COLUMNS (use these exact names in SQL):
        - term (TEXT) -- Academic term code (e.g., '2261')
        - session (TEXT) -- Session number
        - subject (TEXT) -- Course subject code (e.g., 'DKU', 'GERMAN', 'JAPANESE', 'MATH', 'COMPSCI')
        - catalog (TEXT) -- Course catalog number (e.g., '102', '391', '101')
        - section (TEXT) -- Section number (e.g., '001', '002')
        - instructor_name (TEXT) -- Instructor name in 'LastName,FirstName' format (e.g., 'Miller,James', 'Cao,Huansheng')
        - course_title (TEXT) -- Course title/description (e.g., 'Talking Climate Change', 'Beginning German 2')
        - facility_id (TEXT) -- Classroom/facility location (e.g., 'BALLROOM', may be empty)
        - meeting_start (TIME) -- Meeting start time in 'HH:MM:SS AM/PM' format (e.g., '10:00:00 AM', '2:30:00 PM')
        - meeting_end (TIME) -- Meeting end time in 'HH:MM:SS AM/PM' format (e.g., '11:15:00 AM', '4:00:00 PM')
        - days (ARRAY of TEXT) -- List of days when the class meets, e.g., ['Mon','Wed','Fri']
        - max_units (NUMERIC) -- Maximum credit units (e.g., 2.00, 4.00)
        - class_type (TEXT) -- Course type/format (e.g., 'CAMP')
        - instructor_email (TEXT) -- Instructor email address
        - preferred (TEXT) -- Preferred email indicator ('Y' or 'N')

        QUERY EXAMPLES:
        1. "What classes does Professor Cao teach on Tuesday?"
        SELECT subject, catalog, course_title, facility_id, meeting_start, meeting_end
        FROM dku_class_schedule
        WHERE LOWER(instructor_name) ILIKE '%cao%' AND 'Tues' = ANY(days)
        LIMIT 50;

        2. "Monday classes at 10am"
        SELECT subject, catalog, course_title, instructor_name, facility_id
        FROM dku_class_schedule
        WHERE 'Mon' = ANY(days)
        AND (meeting_start = '10:00:00 AM' OR meeting_start LIKE '10:%AM')
        LIMIT 50;

        3. "German courses"
        SELECT subject, catalog, section, course_title, instructor_name, meeting_start, meeting_end, days
        FROM dku_class_schedule
        WHERE LOWER(subject) ILIKE '%german%'
        LIMIT 50;

        4. "Tuesday/Thursday afternoon classes"
        SELECT subject, catalog, course_title, instructor_name, meeting_start, meeting_end
        FROM dku_class_schedule
        WHERE ('Tues' = ANY(days) OR 'Thurs' = ANY(days))
        AND CAST(meeting_start AS TIME) BETWEEN '12:00:00'::time AND '17:00:00'::time
        LIMIT 50;

        5. "MWF morning classes"
        SELECT subject, catalog, course_title, instructor_name, meeting_start, meeting_end
        FROM dku_class_schedule
        WHERE days @> ARRAY['Mon','Wed','Fri']::text[]
        AND CAST(meeting_start AS TIME) < '12:00:00'::time
        LIMIT 50;

        6. "MATH 101 schedule"
        SELECT section, instructor_name, facility_id, meeting_start, meeting_end, days
        FROM dku_class_schedule
        WHERE subject ILIKE '%math%' AND catalog = '101'
        LIMIT 50;

        7. "Classes in BALLROOM"
        SELECT subject, catalog, course_title, instructor_name, meeting_start, meeting_end, days
        FROM dku_class_schedule
        WHERE LOWER(facility_id) ILIKE '%ballroom%'
        LIMIT 50;

        8. "What does Professor Miller teach?"
        SELECT subject, catalog, course_title, facility_id, meeting_start, meeting_end, days
        FROM dku_class_schedule
        WHERE LOWER(instructor_name) ILIKE '%miller%'
        LIMIT 50;

        TIME MATCHING TIPS:
        - For exact time: mtg_start = '10:00:00 AM'
        - For time range: mtg_start BETWEEN '9:00:00 AM' AND '11:00:00 AM'
        - Morning (before noon): CAST(mtg_start AS TIME) < '12:00:00'::time
        - Afternoon (12pm-5pm): CAST(mtg_start AS TIME) BETWEEN '12:00:00'::time AND '17:00:00'::time
        - Evening (after 5pm): CAST(mtg_start AS TIME) >= '17:00:00'::time

        INSTRUCTOR NAME TIPS:
        - Format is 'LastName,FirstName' (e.g., 'Miller,James')
        - For search, use: LOWER(name) ILIKE '%lastname%' OR LOWER(name) ILIKE '%firstname%'
        - Don't assume column is called 'instructor_name' - it's just 'name'

        FACILITIES MAPPING:
        - BALLROOM -> Academic Building Ballroom
        - ACAD -> Academic Building (or AB)
        - INNO -> Innovation Building (or IB) 
        - CCTE -> Community Center East (or CCTE)
        - LIB -> Library
        - WDR -> Wuhan-Duke Research Building
        - CC -> Conference Center
        - USR -> Undergraduate Student Residence

        SESSION MAPPING:
        - 1    -> 14 weeks (2 sessions)
        - 7W1  -> Session 1 (7 weeks)
        - 7W2  -> Session 2 (7 weeks)
        - MNS  -> Mini-Session (1 week)
        """
    
    return schema_desc


connection = psycopg2.connect(
    database="chatdku_db",  # Your database name
    user="chatdku_user",  # Your username
    password=os.getenv("DB_PWD"),  # Your password
    host="localhost",  # Host address (often "localhost")
    port="5432",  # Default PostgreSQL port
)

schema = fetch_course_schedule_schema(connection)
# print(schema)