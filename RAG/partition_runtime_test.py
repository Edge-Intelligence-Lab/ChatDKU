from unstructured.partition.auto import partition as original_partition
from custom_partation import partition as custom_partition

import time

def measure_time(partition_func, file_path):
    start_time = time.time()
    partition_func(file_path)
    end_time = time.time()
    return end_time - start_time

def main():
    file_path = "../RAG_data/student_handbook/student_handbook_2023-08-16.pdf"
    print(f"Original partition test start...\n")
    
    original_time = measure_time(original_partition, file_path)
    
    print(f"Original partition method time: {original_time:.4f} seconds\n")

    print(f"Custom partition test start...\n")
    
    new_time = measure_time(custom_partition, file_path) 
    
    print(f"Custom partition method time: {new_time:.4f} seconds\n")

if __name__ == "__main__":
    main()
