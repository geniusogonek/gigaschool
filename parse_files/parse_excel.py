import pandas as pd
import re
from datetime import datetime


def parse_schedule_excel(file_path, class_number):
    LOAD_LEVELS = {
        "РОВ": 1,
        "история": 5,
        "физика": 8,
        "англ/инф": 6,
        "рус.яз": 6,
        "инф/англ": 6,
        "алгебра": 9,
        "родн.яз": 6,
        "химия": 8,
        "литер": 6,
        "географ": 5,
        "англ.яз": 6,
        "труд": 4,
        "физ-ра": 3,
        "геомет": 9,
        "биолог": 6,
        "кл.час": 1,
        "вер и ст": 7,
        "профмин": 2,
        "ОБЗР": 4,
        "обществ": 5,
        "---": 0
    }
    
    def clean_cell_value(value):
        if pd.isna(value) or value in ['---', '----', '-----', '', ' ']:
            return None
        return str(value).strip()

    def extract_lesson_info(cell_value):
        if not cell_value:
            return None, None

        parts = cell_value.split('\n')
        
        if len(parts) >= 2:
            lesson = parts[0].strip()
            classroom = parts[1].strip()
            return lesson, classroom
        else:
            return cell_value, None

    def get_load_level(lesson_name):
        if not lesson_name or lesson_name == "---":
            return 0
        return LOAD_LEVELS.get(lesson_name, 5)

    def extract_date_from_sheet(df):
        for i in range(min(10, len(df))):
            for col in df.columns:
                cell = df.iloc[i][col]

                if isinstance(cell, datetime):
                    return cell.strftime('%d.%m.%Y')

                cell_str = str(cell)
                if 'на' in cell_str.lower() and ('2025' in cell_str or '2024' in cell_str):
                    date_match = re.search(r'(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}\.\d{2}\.\d{4})', cell_str)
                    if date_match:
                        date_str = date_match.group(1)
                        try:
                            if '-' in date_str:
                                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                            else:
                                date_obj = datetime.strptime(date_str, '%d.%m.%Y')
                            return date_obj.strftime('%d.%m.%Y')
                        except:
                            pass

        for i in range(min(10, len(df))):
            for col_idx in range(len(df.columns) - 1):
                cell = str(df.iloc[i][col_idx])
                next_cell = df.iloc[i][col_idx + 1]
                
                if 'на' in cell.lower() and isinstance(next_cell, datetime):
                    return next_cell.strftime('%d.%m.%Y')
        
        return None

    excel_file = pd.ExcelFile(file_path)
    results = []
    
    for sheet_name in excel_file.sheet_names:
        if sheet_name == 'Лист15':
            continue

        df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)

        date = extract_date_from_sheet(df)
        if not date:
            print(f"не удалось найти дату на листе '{sheet_name}'")
            continue

        header_row = None
        for i in range(min(15, len(df))):
            if 'класс' in str(df.iloc[i][0]).lower():
                header_row = i
                break
        
        if header_row is None:
            print(f"не удалось найти строку 'класс' на листе '{sheet_name}'")
            continue

        class_row = None
        for i in range(header_row + 1, len(df)):
            cell_value = clean_cell_value(df.iloc[i][0])
            if cell_value and class_number in cell_value:
                class_row = i
                break

        if class_row is None:
            continue

        lessons = []
        max_lesson_number = 0

        for col_idx in range(1, len(df.columns)):
            cell_value = clean_cell_value(df.iloc[class_row][col_idx])

            if cell_value:
                lesson_name, classroom = extract_lesson_info(cell_value)
                if lesson_name:
                    max_lesson_number = max(max_lesson_number, col_idx)

        for col_idx in range(1, max_lesson_number + 1):
            cell_value = clean_cell_value(df.iloc[class_row][col_idx])

            if cell_value:
                lesson_name, classroom = extract_lesson_info(cell_value)
                lessons.append({
                    "lesson": lesson_name if lesson_name else "---",
                    "classroom": classroom if classroom else "",
                    "lesson_number": col_idx,
                    "load_level": get_load_level(lesson_name)
                })
            else:
                lessons.append({
                    "lesson": "---",
                    "classroom": "",
                    "lesson_number": col_idx,
                    "load_level": 0
                })

        if lessons:
            results.append({
                "date": date,
                "lessons": lessons
            })

    return results


if __name__ == "__main__":
    schedule_9a = parse_schedule_excel('schedule.xlsx', '9А')
    print(schedule_9a)
