import os
import random
import string

def get_desktop_path():
    return os.path.join(os.environ['USERPROFILE'], 'Desktop')

def main():
    try:
        desktop = get_desktop_path()
        folder_name = "测试文件夹"
        folder_path = os.path.join(desktop, folder_name)
        
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        
        for i in range(1, 6):
            file_path = os.path.join(folder_path, f"random_{i}.txt")
            content = ''.join(random.choices(string.ascii_letters + string.digits, k=50))
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        print(f"Successfully created 5 files in {folder_path}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()