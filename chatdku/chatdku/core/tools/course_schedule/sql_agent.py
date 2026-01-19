import dspy
import re
from .get_schema import fetch_course_schedule_schema


# -------------------------
# Safety utilities
# -------------------------

def sanitize_sql(sql: str) -> str:
    if not sql:
        return "SELECT 'INSUFFICIENT_INFO';"

    sql = sql.strip()

    # only SELECT
    if not sql.lower().startswith("select"):
        return "SELECT 'UNAUTHORIZED';"

    # forbid mutation
    forbidden = [
        "insert", "update", "delete", "drop", "truncate",
        "alter", "create", "replace", "grant", "revoke",
        "copy", "vacuum", "analyze"
    ]
    lowered = f" {sql.lower()} "
    for kw in forbidden:
        if f" {kw} " in lowered:
            return "SELECT 'UNAUTHORIZED';"

    # enforce LIMIT
    if "limit" not in lowered:
        raise ValueError("LIMIT is required")

    return sql



def safe_execute(conn, sql: str):
    sql = sanitize_sql(sql)

    if "unauthorized" in sql.lower():
        return [], []

    if "insufficient_info" in sql.lower():
        return [], []

    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return rows, cols
    
    
def extract_sql_regex(text):
    # Case-insensitive extraction from "sql: " followed by anything until ";"
    pattern = r"sql:\s*(.*?);"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)

    if match:
        return match.group(1).strip() + ";"
    else:
        return text
    
def preprocess_query(query: str) -> dict:
    """
    Extract and normalize search terms from natural language query.
    """
    import re
    
    # 提取课程代码模式 (e.g., "MATH 101", "COMPSCI221")
    course_code_pattern = r'\b([A-Z]{2,10})\s*(\d{3,4}[A-Z]?)\b'
    course_codes = re.findall(course_code_pattern, query, re.IGNORECASE)
    
    # 标准化课程代码（移除空格）
    normalized_codes = [''.join(code).upper() for code in course_codes]
    
    # 提取可能的教授名字
    # 简单实现：检测大写开头的连续单词
    name_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b'
    names = re.findall(name_pattern, query)
    
    return {
        "original_query": query,
        "course_codes": normalized_codes,
        "names": names,
        "normalized_query": query.lower().strip()
    }

def enhance_sql_fuzzy_matching(sql: str) -> str:
    """
    Post-process generated SQL to add fuzzy matching if missing.
    """
    import re
    
    # 如果已经有 ILIKE，直接返回
    if 'ILIKE' in sql.upper():
        return sql
    
    # 替换 = 为 ILIKE（针对文本字段）
    # 简单实现：查找 WHERE xxx = 'value' 模式
    pattern = r"(\w+)\s*=\s*'([^']+)'"
    
    def replacer(match):
        column = match.group(1)
        value = match.group(2)
        # 添加通配符
        return f"{column} ILIKE '%{value}%'"
    
    enhanced_sql = re.sub(pattern, replacer, sql, flags=re.IGNORECASE)
    
    return enhanced_sql



class Text2SQLSignature(dspy.Signature):
    """
    Generate PostgreSQL SELECT with proper time/day handling.

    CRITICAL - TIME COLUMNS:
    - Times: mtg_start, mtg_end (format: 'HH:MM:SS AM/PM')
    
    TIME MATCHING RULES:
    - "10am" → WHERE mtg_start = '10:00:00 AM' OR mtg_start LIKE '10:%AM'
    - "morning" → WHERE CAST(mtg_start AS TIME) < '12:00:00'::time
    - "afternoon" → WHERE CAST(mtg_start AS TIME) BETWEEN '12:00:00'::time AND '17:00:00'::time
    - "evening" → WHERE CAST(mtg_start AS TIME) >= '17:00:00'::time
    - "2-4pm" → WHERE mtg_start >= '2:00:00 PM' AND mtg_end <= '4:00:00 PM'
    
    COMBINE DAY + TIME:
    - Always use AND to combine day and time conditions
    - Example: "Monday at 10am" → 
        WHERE 'Mon' = ANY(days)
        AND (meeting_start = '10:00:00 AM' OR meeting_start LIKE '10:%AM')
    
    OTHER RULES:
    - Only SELECT statements
    - Always LIMIT <= 50
    - Use ILIKE for fuzzy text matching
    """

    natural_language_query = dspy.InputField(desc="User's natural language question")
    sql_context = dspy.InputField(desc="PostgreSQL table schema.")
    sql = dspy.OutputField(desc="Pure, valid PostgreSQL query ending with semicolon")


class SQLResult2Text(dspy.Signature):
    """
    Convert SQL query results into a helpful natural language answer.
    If result is empty, explain why.

    ENHANCEMENTS:
    - If result is empty, explain why (e.g., no matching instructor, time, or day)
    - Map `session` codes to descriptive text:
        1    -> "14 weeks (2 sessions)"
        7W1  -> "Session 1 (7 weeks)"
        7W2  -> "Session 2 (7 weeks)"
    - Map `facility_id` abbreviations to full names using FACILITIES MAPPING.
    - Convert `days` array into human-readable string (e.g., ['Mon','Wed'] -> "Monday and Wednesday")
    """
    question = dspy.InputField()
    columns = dspy.InputField()
    rows = dspy.InputField()
    answer = dspy.OutputField()

    def execute(self, question, columns, rows):
        if not rows:
            return f"Sorry, no results found for your query: '{question}'"

        result_texts = []
        SESSION_MAP = {
            "1": "14 weeks (2 sessions)",
            "7W1": "Session 1 (7 weeks)",
            "7W2": "Session 2 (7 weeks)",
            "MNS": "Mini-Session (1 week)"
        }

        FACILITY_MAP = {
            "BALLROOM": "Academic Building Ballroom",
            "ACAD3101": "Academic Building (or AB) 3101",
            "INNO2052": "Innovation Building (or IB) 2052",
            "CCTE2012": "Community Center East (or CCTE)",
            "LIB1115": "Library",
            "WDR1100": "Wuhan-Duke Research Building",
            "CC1011": "Conference Center",
            "USR": "Undergraduate Student Residence"
        }

        for row in rows:
            # Map session
            session_text = SESSION_MAP.get(row.get("session"), row.get("session"))
            # Map facility
            facility_text = FACILITY_MAP.get(row.get("facility_id"), row.get("facility_id"))
            # Convert days array to readable string
            days_list = row.get("days", [])
            days_text = ", ".join(days_list) if days_list else "N/A"

            line = f"{row.get('course_title')} ({row.get('subject')} {row.get('catalog')}, Session: {session_text}) " \
                   f"taught by {row.get('instructor_name')}, meets on {days_text} from {row.get('meeting_start')} to {row.get('meeting_end')} " \
                   f"in {facility_text}."
            result_texts.append(line)

        return "\n".join(result_texts)


# -------------------------
# SQL Generator
# -------------------------
class GenerateSQL(dspy.Module):
    def __init__(self):
        super().__init__()
        self.sql_generator = dspy.ChainOfThought(Text2SQLSignature)
        
        self.demos = [
            dspy.Example(
                natural_language_query="Find MATH101",
                sql_context="courses(course_code TEXT, title TEXT)",
                sql="SELECT * FROM courses WHERE REPLACE(course_code, ' ', '') ILIKE '%MATH101%' LIMIT 50;"
            ).with_inputs("natural_language_query", "sql_context"),
            
            dspy.Example(
                natural_language_query="Classes by Prof. Smith",
                sql_context="classes(instructor_name TEXT, course_id INT)",
                sql="SELECT * FROM classes WHERE LOWER(instructor_name) ILIKE '%smith%' LIMIT 50;"
            ).with_inputs("natural_language_query", "sql_context"),
        ]

    def _build_enhanced_context(self, query: str, processed: dict, schema: str) -> str:
        """构建包含模糊匹配策略的上下文"""
        context = f"{schema}\n\n"
        
        # 添加检测到的实体
        if processed["course_codes"]:
            context += f"DETECTED COURSE CODES: {', '.join(processed['course_codes'])}\n"
            context += "Use: WHERE REPLACE(course_code, ' ', '') ILIKE '%CODE%'\n\n"
        
        if processed["names"]:
            context += f"DETECTED NAMES: {', '.join(processed['names'])}\n"
            context += "Use: WHERE LOWER(instructor_name) ILIKE '%name%'\n\n"
        
        # 通用模糊匹配策略
        context += """
            REQUIRED FUZZY MATCHING TECHNIQUES:
            1. Course codes: REPLACE(course_code, ' ', '') ILIKE '%{normalized_code}%'
            2. Text fields: LOWER(column) ILIKE LOWER('%{term}%')
            3. Multiple terms: column ILIKE '%term1%' OR column ILIKE '%term2%'
            4. Partial matches: Always use % wildcards unless exact match is explicitly required

            EXAMPLE QUERIES:
            Q: "Find MATH 101"
            A: SELECT * FROM courses WHERE REPLACE(course_code, ' ', '') ILIKE '%MATH101%' LIMIT 50;

            Q: "Classes taught by John Smith"
            A: SELECT * FROM classes WHERE LOWER(instructor_name) ILIKE '%john%smith%' LIMIT 50;

            Q: "Intro to Computer Science"
            A: SELECT * FROM courses WHERE title ILIKE '%intro%computer%science%' OR description ILIKE '%intro%computer%science%' LIMIT 50;
            """
        
        return context
    
    def forward(self, query, db_schema: str):
        # 1. 预处理查询
        processed = preprocess_query(query)
        
        # 2. 构建增强提示
        enhanced_context = self._build_enhanced_context(query, processed, db_schema)
        
        # 3. 生成 SQL
        out = self.sql_generator(
            natural_language_query=query,
            sql_context=enhanced_context,
        )
        
        # 4. 后处理优化
        sql = out.sql.strip()
        sql = enhance_sql_fuzzy_matching(sql)
        
        return sql
    


# -------------------------
# Main Agent
# -------------------------
class SQLAgent(dspy.Module):
    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        self.sql_generator = GenerateSQL()
        self.interpreter = dspy.Predict(SQLResult2Text)

        self.schema = fetch_course_schedule_schema(conn)

    def forward(self, question: str):
        # 1. Generate SQL
        sql = self.sql_generator(
            query=question,
            db_schema=self.schema,
        )

        # 2. Execute safely
        try:
            rows, columns = safe_execute(self.conn, sql)

            # 3. Interpret result
            result = self.interpreter(
                question=question,
                columns=columns,
                rows=rows,
            )
            # print(result["raw_rows"])
            return {
                "sql": sql,
                "answer": result.answer,
                "raw_rows": rows,
                "columns": columns
            }
        
        except Exception as e:
            # 错误时也返回一个友好的 answer
            return {
                "sql": sql,
                "error": str(e),
                "answer": f"Sorry, I encountered an error executing the query: {str(e)}"  # 添加这行
            }