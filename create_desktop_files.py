import os
import random
import string

def write_random_string(filepath):
    length = random.randint(10, 100)
    content = ''.join(random.choices(string.ascii_letters + string.digits + " ", k=length))
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

target_dir = r"C:\Users\win11\Desktop\测试文件夹"
try:
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    for i in range(1, 4):
        filename = f"test_{i}.txt"
        write_random_string(os.path.join(target_dir, filename))
    print(f"Successfully created 3 files in {target_dir}")
except Exception as e:
    print(f"Error: {e}")
