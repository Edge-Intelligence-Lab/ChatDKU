"""
Used to load test the retriever
Generated using Claude Sonnet 4.5
"""

import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List

from chatdku.core.tools.llama_index import DocRetrieverOuter

DocumentRetriever = DocRetrieverOuter({})


@dataclass
class QueryResult:
    thread_id: int
    query_size: str
    semantic_query: str
    success: bool
    elapsed_time: float
    num_results: int
    error: str = None


def test_concurrent_queries(num_users: int = 3, rounds: int = 3):
    """
    Load test with multiple concurrent users making queries of different sizes.

    Args:
        num_users: Number of concurrent users to simulate
        rounds: Number of rounds each user will query
    """

    # Query templates of different sizes
    QUERY_TEMPLATES = {
        "small": [
            ("hello", "COMPSCI"),
            ("advisor", "courses"),
            ("requirements", "prerequisites"),
        ],
        "medium": [
            ("How often should I visit my advisor?", "machine learning courses"),
            ("What are the graduation requirements?", "software engineering electives"),
            ("When should I register for classes?", "course registration deadlines"),
        ],
        "large": [
            (
                "What are the courses of Applied Mathematics and what prerequisites do I need?",
                "applied mathematics prerequisites requirements",
            ),
            (
                "I'm interested in machine learning and artificial intelligence. What courses should I take?",
                "machine learning AI courses curriculum path",
            ),
            (
                "Can you explain the difference between software engineering and computer science programs?",
                "software engineering vs computer science degree requirements",
            ),
        ],
        "extra_large": [
            (
                """The professor sent me this as requirement to be my SW mentor:
                Please send me your CV and transcript.
                In particular, please send me your planned proposal draft and try your best to answer the following:
                Research topic and key question,
                Existing works and their limitation,
                Your Idea and workplan
                Once I received the above, I will schedule an in-person meeting with you.
                What do I need to do?""",
                "senior project advisor requirements CV transcript proposal research",
            ),
        ],
    }

    def user_query_task(user_id: int, round_num: int) -> QueryResult:
        """Simulate a single user making a query"""
        # Vary query sizes across users and rounds
        query_sizes = ["small", "medium", "large", "extra_large"]
        size_idx = (user_id + round_num) % len(query_sizes)
        query_size = query_sizes[size_idx]

        # Select a query from the size category
        queries = QUERY_TEMPLATES[query_size]
        query_idx = user_id % len(queries)
        semantic_q, keyword_q = queries[query_idx]

        start_time = time.time()
        results, internal = DocumentRetriever(semantic_q, keyword_q)
        elapsed = time.time() - start_time

        success = True if len(results) == 10 else False

        return QueryResult(
            thread_id=user_id,
            query_size=query_size,
            semantic_query=(
                semantic_q[:50] + "..." if len(semantic_q) > 50 else semantic_q
            ),
            success=success,
            elapsed_time=elapsed,
            num_results=len(results),
        )

    print(f"🚀 Starting load test: {num_users} concurrent users, {rounds} rounds each")
    print(f"📊 Total queries: {num_users * rounds}\n")

    all_results: List[QueryResult] = []
    overall_start = time.time()

    # Execute queries concurrently
    with ThreadPoolExecutor(max_workers=num_users) as executor:
        futures = []
        for round_num in range(rounds):
            for user_id in range(num_users):
                future = executor.submit(user_query_task, user_id, round_num)
                futures.append(future)

            # Collect results as they complete
            for future in as_completed(futures):
                result = future.result()
                all_results.append(result)

                status = "✓" if result.success else "✗"
                print(
                    f"{status} User {result.thread_id:2d} | {result.query_size:12s} | "
                    f"{result.elapsed_time:5.2f}s | {result.num_results:3d} results"
                )

    overall_elapsed = time.time() - overall_start

    # Analyze results
    print("\n" + "=" * 70)
    print("📈 LOAD TEST RESULTS")
    print("=" * 70)

    successful = [r for r in all_results if r.success]
    failed = [r for r in all_results if not r.success]

    print(
        f"\n✓ Successful queries: {len(successful)}/{len(all_results)} "
        f"({len(successful)/len(all_results)*100:.1f}%)"
    )
    print(
        f"✗ Failed queries: {len(failed)}/{len(all_results)} "
        f"({len(failed)/len(all_results)*100:.1f}%)"
    )

    if successful:
        times = [r.elapsed_time for r in successful]
        print("\n⏱️  Response Times:")
        print(f"   Average: {sum(times)/len(times):.3f}s")
        print(f"   Min:     {min(times):.3f}s")
        print(f"   Max:     {max(times):.3f}s")
        print(f"   Median:  {sorted(times)[len(times)//2]:.3f}s")

    # Break down by query size
    print("\n📏 Performance by Query Size:")
    by_size = defaultdict(list)
    for r in successful:
        by_size[r.query_size].append(r.elapsed_time)

    for size in ["small", "medium", "large", "extra_large"]:
        if size in by_size:
            times = by_size[size]
            avg = sum(times) / len(times)
            print(f"   {size:12s}: {avg:.3f}s avg ({len(times)} queries)")

    print(f"\n⚡ Throughput: {len(all_results)/overall_elapsed:.2f} queries/second")
    print(f"🕐 Total time: {overall_elapsed:.2f}s")

    if failed:
        print("\n❌ Failed Query Details:")
        for r in failed[:5]:  # Show first 5 failures
            print(f"   User {r.thread_id} ({r.query_size}): {r.error}")

    # Assertions for test validation
    assert len(successful) > 0, "All queries failed"
    assert len(successful) / len(all_results) > 0.8, "Success rate below 80%"

    if successful:
        avg_time = sum(r.elapsed_time for r in successful) / len(successful)
        assert avg_time < 10, f"Average response time too high: {avg_time:.2f}s"

    print("\n✅ Load test completed successfully!")
    return all_results


def test_same_query_concurrent(num_users: int = 3):
    """
    Load test where all users make the SAME query simultaneously.
    Tests caching behavior and concurrent access patterns.
    """

    SAME_QUERY = (
        "What are the machine learning courses available?",
        "machine learning courses prerequisites",
    )

    print(f"🚀 Starting same-query load test: {num_users} users, same query")
    print(f"📝 Query: '{SAME_QUERY[0]}'\n")

    results = []

    def query_task(user_id: int):
        start = time.time()
        docs, internal = DocumentRetriever(SAME_QUERY[0], SAME_QUERY[1])
        elapsed = time.time() - start
        doc_len = len(docs)
        if doc_len == 10:
            success = True
        else:
            doc_len = doc_len - 1
            success = False

        return (user_id, success, elapsed, doc_len, None)

    overall_start = time.time()

    with ThreadPoolExecutor(max_workers=num_users) as executor:
        futures = [executor.submit(query_task, i) for i in range(num_users)]

        for future in as_completed(futures):
            user_id, success, elapsed, num_results, error = future.result()
            results.append((success, elapsed, num_results))

            status = "✓" if success else "✗"
            print(
                f"{status} User {user_id:2d} | {elapsed:5.2f}s | {num_results:3d} results"
            )

    overall_elapsed = time.time() - overall_start

    # Analysis
    print("\n" + "=" * 70)
    print("📈 SAME-QUERY LOAD TEST RESULTS")
    print("=" * 70)

    successful = [r for r in results if r[0]]
    times = [r[1] for r in successful]

    print(
        f"\n✓ Success rate: {len(successful)}/{len(results)} "
        f"({len(successful)/len(results)*100:.1f}%)"
    )

    if times:
        print("\n⏱️  Response Times:")
        print(f"   Average: {sum(times)/len(times):.3f}s")
        print(f"   Min:     {min(times):.3f}s")
        print(f"   Max:     {max(times):.3f}s")
        print(
            f"   Std Dev: {(sum((t-sum(times)/len(times))**2 for t in times)/len(times))**0.5:.3f}s"
        )

    print(f"\n⚡ Throughput: {len(results)/overall_elapsed:.2f} queries/second")
    print(f"🕐 Wall clock time: {overall_elapsed:.2f}s")

    print("\n✅ Same-query load test completed!")
    return results
