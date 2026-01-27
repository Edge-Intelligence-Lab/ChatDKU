from chatdku.core.tools.course_ret import course_retriever


def test_course_retriever():
    __import__("pprint").pprint(course_retriever(["MATH 308"]))
