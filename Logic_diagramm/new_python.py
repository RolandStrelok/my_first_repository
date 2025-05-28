import pytesseract
from pdf2image import convert_from_path
from PIL import Image # Импортируем Image для операций с изображениями
import os
import re
import csv

# --- Настройка путей ---
poppler_path = r'C:\Program Files\poppler-24.08.0\Library\bin'

# --- Путь к вашему PDF-файлу ---
pdf_path = 'C:\Work\Python\Project\Repository\my_first_repository\doc01089520220614124446.pdf' # <--- ОБЯЗАТЕЛЬНО ЗАМЕНИТЕ НА ВАШ ПОЛНЫЙ ПУТЬ К PDF-ФАЙЛУ!

# --- Словарь для хранения результатов ---
# Структура: { номер_страницы: { 'key_text': '...', 'remaining_words': [...] } }
recognized_data_per_page = {}

# --- Координаты целевой области (left, top, right, bottom) ---
# Вам нужно определить эти координаты, просмотрев ваш PDF в графическом редакторе
# или программе просмотра PDF (например, XnView MP, Adobe Acrobat Reader, GIMP).
# Эти координаты должны быть заданы для ОРИГИНАЛЬНОЙ ориентации страницы в PDF.
# (X1, Y1, X2, Y2) - верхний левый угол (X1, Y1), нижний правый угол (X2, Y2)

key_area_coords = (0, 0, 400, 700) # <--- Ключевая область
# <--- ИЗМЕНИТЕ ЭТИ КООРДИНАТЫ ПОД ВАШИ НУЖДЫ!

# --- Настройки для CSV-файла ---
output_csv_filename = 'ocr_key_and_remaining_results_test.csv' # Имя файла
words_internal_delimiter = '; ' 

# --- Вспомогательные функции ---

def contains_digit(word):
    """Проверяет, содержит ли данное слово хотя бы одну цифру."""
    return any(char.isdigit() for char in word)

def extract_and_clean_word(text):
    """
    Приводит текст к нижнему регистру, оставляет буквы, цифры, дефисы и пробелы,
    затем возвращает очищенную строку.
    """
    if not text:
        return ""
    text = text.lower()
    # Оставляем только буквы (Unicode), цифры, пробелы и дефисы
    text = re.sub(r'[^\w\s-]', '', text) 
    return text.strip()

def is_bbox_overlap(bbox1, bbox2):
    """Проверяет, перекрываются ли две ограничивающие рамки."""
    x1_min, y1_min, x1_max, y1_max = bbox1
    x2_min, y2_min, x2_max, y2_max = bbox2

    # Проверка на перекрытие
    if x1_min >= x2_max or x2_min >= x1_max:
        return False
    if y1_min >= y2_max or y2_min >= y1_max:
        return False
    return True

print(f"Начинаем обработку PDF: '{pdf_path}'")
print(f"Координаты ключевой области: {key_area_coords}")
print("Обработка будет выполняться без поворота страниц.")
print("Будут распознаны слова, содержащие цифры, из ключевой области и из всей остальной области страницы.")
print("Убедитесь, что координаты областей заданы для оригинальной ориентации страниц в PDF.")
print("-" * 50)

try:
    print(f"Преобразование PDF '{pdf_path}' в изображения...")
    all_pages = convert_from_path(pdf_path, poppler_path=poppler_path)
    print(f"Обнаружено всего {len(all_pages)} страниц.")

    # --- ТЕСТОВЫЙ РЕЖИМ: ОБРАБАТЫВАЕМ ТОЛЬКО ПЕРВЫЕ 10 СТРАНИЦ ---
    num_pages_to_process = 1
    pages_to_iterate = all_pages[:num_pages_to_process]

    print(f"ВНИМАНИЕ: Активирован тестовый режим. Будет обработано только первые {len(pages_to_iterate)} страниц.")
    print("-" * 50)

    # Преобразуем координаты ключевой области в формат (x_min, y_min, x_max, y_max)
    key_area_bbox = (key_area_coords[0], key_area_coords[1], key_area_coords[2], key_area_coords[3])

    for i, page_image in enumerate(pages_to_iterate):
        page_num = i + 1 # Нумерация страниц начинается с 1
        print(f"\n--- Обработка страницы {page_num} из {len(pages_to_iterate)} ---")

        # Получаем данные о распознанных словах с координатами (Tesseract's default word splitting)
        page_data = pytesseract.image_to_data(page_image, output_type=pytesseract.Output.DICT, lang='rus+eng', config='--psm 3')

        key_words_list = []
        remaining_words_list = []

        # Проходим по всем распознанным "элементам" Tesseract
        for j in range(len(page_data['text'])):
            word_text_raw = page_data['text'][j]
            conf = int(page_data['conf'][j]) # Уверенность распознавания

            # Проверяем, что это реальное слово с хорошей уверенностью
            if word_text_raw.strip() and conf > 50: # Можно настроить порог уверенности
                cleaned_word = extract_and_clean_word(word_text_raw)

                if not cleaned_word: # Если очистка удалила все, пропускаем
                    continue

                # Проверяем, содержит ли слово цифры
                if contains_digit(cleaned_word):
                    x = page_data['left'][j]
                    y = page_data['top'][j]
                    w = page_data['width'][j]
                    h = page_data['height'][j]

                    word_bbox = (x, y, x + w, y + h) # (x_min, y_min, x_max, y_max)

                    # Распределяем слова по областям
                    if is_bbox_overlap(word_bbox, key_area_bbox):
                        key_words_list.append(cleaned_word)
                    else:
                        # Если слово с цифрами не в ключевой области, оно идет в "остальную"
                        remaining_words_list.append(cleaned_word)

        # Формируем ключ для словаря (из слов ключевой области)
        key_text_for_dict = ""
        if key_words_list:
            key_text_for_dict = " ".join(key_words_list)
            if len(key_text_for_dict) > 150: # Обрезаем для читаемости ключа
                key_text_for_dict = key_text_for_dict[:70] + "..." + key_text_for_dict[-70:]
        else:
            key_text_for_dict = "NO_DIGIT_KEY_WORD_FOUND" # Если нет слов, подходящих под критерии для ключа

        # Делаем списки слов уникальными и сортируем для консистентности
        remaining_unique_sorted = list(sorted(set(remaining_words_list)))

        # --- 4. Сохраняем результат в словаре ---
        recognized_data_per_page[page_num] = {
            'key_text': key_text_for_dict,
            'remaining_words': remaining_unique_sorted
        }

        print(f"   -> Ключ для страницы {page_num}: '{key_text_for_dict}'")
        print(f"   -> Найдено {len(remaining_unique_sorted)} слов (с цифрами) в остальной области.")

except Exception as e:
    print(f"\nКРИТИЧЕСКАЯ ОШИБКА при обработке PDF: {e}")
    import traceback
    traceback.print_exc() # Вывод полного стека ошибок
    print("Убедитесь, что Tesseract-OCR и Poppler установлены корректно и пути к ним указаны верно.")
    print("Также проверьте, что PDF-файл существует и не поврежден.")


# --- Вывод окончательных результатов в консоль ---
print("\n" + "=" * 60)
print("--- ОКОНЧАТЕЛЬНЫЕ РЕЗУЛЬТАТЫ РАСПОЗНАВАНИЯ В КОНСОЛИ ---")
print("=" * 60)

if recognized_data_per_page:
    # Сортируем по номеру страницы для более удобного просмотра
    sorted_page_nums = sorted(recognized_data_per_page.keys())

    for page_num in sorted_page_nums:
        page_data_dict = recognized_data_per_page[page_num]
        print(f"\n--- Страница {page_num} ---")
        print(f"Ключ (текст с цифрами): '{page_data_dict['key_text']}'")

        display_words_limit = 20

        display_remaining_words = page_data_dict['remaining_words'][:display_words_limit]
        print(f"Остальные слова (с цифрами): {display_remaining_words}{'...' if len(page_data_dict['remaining_words']) > display_words_limit else ''}")
        print(f"Всего остальных слов: {len(page_data_dict['remaining_words'])}")
        print("-" * 60)
else:
    print("Результатов распознавания нет. Возможно, PDF пуст, или произошла ошибка во время обработки.")

# --- Сохранение результатов в CSV файл ---
print(f"\nСохранение результатов в CSV файл: '{output_csv_filename}'")
try:
    with open(output_csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        csv_writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        csv_writer.writerow([
            'Page Number', 
            'Key Text (Digits)', 
            'Remaining Words (Digits)'
        ])

        sorted_page_nums = sorted(recognized_data_per_page.keys())
        for page_num in sorted_page_nums:
            page_data_dict = recognized_data_per_page[page_num]

            # Объединяем списки слов в строки для CSV
            key_text_str = page_data_dict['key_text']
            remaining_words_str = words_internal_delimiter.join(page_data_dict['remaining_words'])

            csv_writer.writerow([page_num, key_text_str, remaining_words_str])
    print(f"Результаты успешно сохранены в '{output_csv_filename}'.")
except IOError as e:
    print(f"Ошибка при сохранении CSV файла: {e}")

print("\nОбработка завершена.")
