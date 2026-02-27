import os
import psycopg2
from psycopg2.extras import Json
import json
from llama_cloud_services.extract import LlamaExtract, ExtractConfig


# Folder containing PDF syllabi
PDF_FOLDER = os.getenv("SYLLABI_PDF_FOLDER", "./data/syllabi")

# SCHEMA IS NOT AUTOMATICALLY GENERATED BECAUSE JSON ALLOWS FOR LLAMAEXTRACT TO HAVE MORE CONTEXT INFO ABOUT EACH DATA FIELD.
# Path to JSON schema matching the PostgreSQL table
SCHEMA_PATH = os.getenv("SYLLABI_SCHEMA_PATH", "classes_schema.json")
with open(SCHEMA_PATH, "r") as f:
    schema_dict = json.load(f)


# Database connection info
DB_CONFIG = {
    "dbname": os.getenv("SYLLABI_DB_NAME", "chatdku_db"),
    "user": os.getenv("SYLLABI_DB_USER", "chatdku_user"),
    "password": os.getenv("SYLLABI_DB_PASSWORD", ""),
    "host": os.getenv("SYLLABI_DB_HOST", "localhost"),
    "port": int(os.getenv("SYLLABI_DB_PORT", "5432")),
}

# --- MAIN LOGIC ---


def get_pdf_files(folder):
    """Recursively get all PDF files in folder and subfolders"""
    pdf_files = []
    for root, _, files in os.walk(folder):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_files.append(os.path.join(root, file))
    return pdf_files


llama_extract_api_key = os.getenv("LLAMA_EXTRACT_API_KEY")
if not llama_extract_api_key:
    raise RuntimeError(
        "LLAMA_EXTRACT_API_KEY is not set. Set it to enable syllabi extraction."
    )

llama_extract = LlamaExtract(api_key=llama_extract_api_key)

config = ExtractConfig(use_reasoning=False)

extractor = llama_extract.create_agent(
    name="syllabi-parser-v2", data_schema=schema_dict, config=config
)
# extractor = llama_extract.get_agent(name="syllabi-parser-v2")


def extract():
    parsed_data = []
    pdf_files = get_pdf_files(PDF_FOLDER)  # Get PDFs recursively
    for pdf_file in pdf_files:
        print(f"Processing file: {pdf_file}")
        with open(pdf_file, "rb") as f:
            try:
                structured = extractor.extract(f)
                print(f"Extracted data: {structured}")
                if not structured or not structured.data:
                    print(f"Warning: No data extracted from {pdf_file}")
                    continue
                if not structured.data.get("course_id"):
                    print(
                        f"Warning: No course_id found in extracted data from {pdf_file}"
                    )
                    continue
                parsed_data.append(structured.data)
            except Exception as e:
                print(f"Error extracting data from {pdf_file}: {str(e)}")
    print(f"Total successfully parsed files: {len(parsed_data)}")
    return parsed_data


def upsert_class(cur, class_obj):
    # TODO: Dynamically update the db instead of batch update.
    print(f"Attempting to insert/update course: {class_obj.get('course_id')}")
    # Convert arrays and objects to proper PostgreSQL format
    for key, value in class_obj.items():
        if isinstance(value, list):
            # Keep lists as they are - psycopg2 handles array conversion
            pass
        elif isinstance(value, dict):
            class_obj[key] = Json(value)
        elif value == "":
            class_obj[key] = None
    insert_stmt = """
    INSERT INTO classes (
        course_code, course_title, credit_hours, course_format, prerequisites, description,
        learning_outcomes, required_textbook, optional_textbooks, academic_policies,
        instructor_email, instructor_name, office_location,
        office_hours, biography, year, semester, semester_session, schedule_days, 
        schedule_time_start, schedule_time_end, location, recitation_time, 
        recitation_location, lab_time, lac_location, grading_policy,
        grade_scale, assignment_policy, communication_policy, teaching_methods
    )
    VALUES (
        %(course_code)s, %(course_title)s, %(credit_hours)s, %(course_format)s, 
        %(prerequisites)s, %(description)s,
        %(learning_outcomes)s, %(required_textbook)s, %(optional_textbooks)s, 
        %(academic_policies)s,
        %(instructor_email)s, %(instructor_name)s, %(office_location)s,
        %(office_hours)s, %(biography)s, %(year)s, %(semester)s, %(semester_session)s, 
        %(schedule_days)s, %(schedule_time_start)s, %(schedule_time_end)s,
        %(location)s, %(recitation_time)s, %(recitation_location)s, %(lab_time)s,
        %(lac_location)s, %(grading_policy)s,
        %(grade_scale)s, %(assignment_policy)s, %(communication_policy)s, 
        %(teaching_methods)s
    );
    """
    try:
        cur.execute(insert_stmt, class_obj)
        print(f"Successfully inserted/updated course: {class_obj.get('course_id')}")
    except Exception as e:
        print(f"Database error for course {class_obj.get('course_id')}:")
        print(f"Error details: {str(e)}")
        print(f"Data that failed: {json.dumps(class_obj, default=str)}")
        raise


def test_db_connection():
    """Test database connection and print relevant information"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Test if we can execute queries
        cur.execute("SELECT current_database(), current_user, version();")
        db, user, version = cur.fetchone()
        print("Successfully connected to database:")
        print(f"Database: {db}")
        print(f"User: {user}")
        print(f"PostgreSQL version: {version}")

        # Test if the classes table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename = 'classes'
            );
        """)
        table_exists = cur.fetchone()[0]
        if not table_exists:
            print("WARNING: 'classes' table does not exist!")

        cur.close()
        conn.close()
        return True
    except psycopg2.Error as e:
        print("Database connection error:")
        print(f"Error code: {e.pgcode}")
        print(f"Error message: {e.pgerror}")
        print(f"Details: {str(e)}")
        return False


def main():
    try:
        if not test_db_connection():
            print(
                "Failed to connect to database. Please check your database configuration."
            )
            return

        pdf_files = get_pdf_files(PDF_FOLDER)
        print(f"Found {len(pdf_files)} PDF files in {PDF_FOLDER}")
        if not pdf_files:
            print(f"No PDF files found in directory: {os.path.abspath(PDF_FOLDER)}")
            return

        parsed_classes = extract()
        print(f"Parsed {len(parsed_classes)} records from PDFs")
        if not parsed_classes:
            print("No data was successfully parsed from PDFs")
            return

        try:
            conn = psycopg2.connect(**DB_CONFIG)
            psycopg2.extras.register_default_json(globally=True, loads=json.loads)
            cur = conn.cursor()
        except psycopg2.Error as e:
            print("Failed to establish database connection:")
            print(f"Error code: {e.pgcode}")
            print(f"Error message: {e.pgerror}")
            return

        success_count = 0
        for class_obj in parsed_classes:
            try:
                upsert_class(cur, class_obj)
                success_count += 1
            except Exception as e:
                print(f"Failed to insert/update course: {class_obj.get('course_id')}")
                print(f"Due to error: {e}")
                continue

        conn.commit()
        cur.close()
        conn.close()
        print(
            f"Sync complete! Successfully processed {success_count} out of {len(parsed_classes)} records"
        )
    except Exception as e:
        print(f"Major error occurred: {str(e)}")
        raise


if __name__ == "__main__":
    main()
