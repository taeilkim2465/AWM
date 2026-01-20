import json
import glob
import os
import argparse

def count_rm_values(base_path):
    # 패턴 설정: webarena.* 폴더 안의 특정 파일명
    search_pattern = os.path.join(base_path, "webarena.*", "gpt-5-mini_autoeval.json")
    
    true_count = 0
    false_count = 0
    files_found = 0

    # 패턴에 매칭되는 모든 파일 탐색
    for file_path in glob.glob(search_pattern):
        files_found += 1
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # 데이터가 리스트 형태인 경우 각 요소의 'rm' 키 확인
                if isinstance(data, list):
                    for item in data:
                        rm_val = item.get("rm")
                        if rm_val is True:
                            true_count += 1
                        elif rm_val is False:
                            false_count += 1
        except (json.JSONDecodeError, IOError) as e:
            print(f"파일 읽기 오류 ({file_path}): {e}")

    print("-" * 30)
    print(f"탐색된 파일 개수: {files_found}")
    print(f"true 개수  : {true_count}")
    print(f"false 개수 : {false_count}")
    total_count = true_count + false_count
    if total_count > 0:
        ratio = true_count / total_count
        print(f"true/total 비율 : {ratio:.4f}")
    else:
        print(f"true/total 비율 : N/A (총 개수 0)")
    print("-" * 30)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Count 'rm' values in autoeval.json files for a specific site.")
    parser.add_argument("--site", type=str, required=True, help="The name of the site to count scores for (e.g., 'shopping', 'gitlab').")
    args = parser.parse_args()

    # 실제 파일이 위치한 부모 경로를 입력하세요.
    # 예: "C:/projects/eval" 또는 "/home/user/eval"
    path_to_search = f"./results/{args.site}" 
    count_rm_values(path_to_search)