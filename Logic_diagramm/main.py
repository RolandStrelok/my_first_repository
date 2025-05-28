import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import os
import re
import string
import csv # Импортируем модуль csv


# Укажите путь к папке 'bin' внутри директории Poppler
# (например, C:\Program Files\poppler\bin). Poppler необходим для pdf2image.


# --- Путь к вашему PDF-файлу ---
pdf_path = 'C:\Work\Python\Project\Repository\my_first_repository\Logic_diagramm\DCS LOGIC DIAGRAM - AMMONIA UTILITIES.pdf' # <--- ОБЯЗАТЕЛЬНО ЗАМЕНИТЕ НА ВАШ ПОЛНЫЙ ПУТЬ К PDF-ФАЙЛУ!

# --- Словарь для хранения результатов ---
# Структура: { (ключ_из_области_str, номер_страницы_int): [список_уникальных_слов_из_оставшейся_части_страницы_list] }
recognized_data_per_page = {}

# --- Координаты целевой области для ключа (left, top, right, bottom) ---
# Вам нужно определить эти координаты, просмотрев ваш PDF в графическом редакторе
# или программе просмотра PDF (например, XnView MP, Adobe Acrobat Reader, GIMP).
# (X1, Y1, X2, Y2) - верхний левый угол (X1, Y1), нижний правый угол (X2, Y2)
# Пример: область от 100 пикселей справа, 100 пикселей сверху, до 700 пикселей справа и 200 пикселей сверху.
key_area_coords = (0, 0, 1920, 200) # <--- ИЗМЕНИТЕ ЭТИ КООРДИНАТЫ ПОД ВАШИ НУЖДЫ!

# --- Настройки для CSV-файла ---
output_csv_filename = 'ocr_results.csv'
# Разделитель для слов внутри ячейки "Оставшиеся слова" в CSV
words_internal_delimiter = '; ' 

# Функция для очистки текста и извлечения слов
def extract_and_clean_words(text):
    """
    Приводит текст к нижнему регистру, удаляет знаки препинания и разбивает на слова.
    """
    if not text:
        return []
    # Приводим к нижнему регистру
    text = text.lower()
    # Удаляем знаки препинания (можно расширить string.punctuation, если нужно)
    text = text.translate(str.maketrans('', '', string.punctuation))
    # Разбиваем на слова по пробелам и фильтруем пустые строки
    words = [word for word in text.split() if word]
    return words

print(f"Начинаем обработку PDF: '{pdf_path}'")
print(f"Координаты ключевой области: {key_area_coords}")
print("-" * 50)

try:
    # Преобразуем PDF в список изображений (по одной картинке на страницу)
    print(f"Преобразование PDF '{pdf_path}' в изображения...")
    pages = convert_from_path(pdf_path, poppler_path=poppler_path)
    print(f"Обнаружено {len(pages)} страниц.")

    for i, page_image in enumerate(pages):
        page_num = i + 1
        print(f"\n--- Обработка страницы {page_num} из {len(pages)} ---")

        # --- 1. Распознаем текст из целевой области для ключа ---
        key_text_for_dict = ""
        cleaned_key_text_for_comparison = "" # Отдельная переменная для сравнения слов (без обрезки)

        try:
            # Обрезаем изображение страницы до нужной ключевой области
            cropped_key_image = page_image.crop(key_area_coords)

            # При желании можно сохранить обрезанное изображение для отладки
            # cropped_key_image.save(f"debug_cropped_key_area_page_{page_num}.png")

            key_text_raw = pytesseract.image_to_string(cropped_key_image, lang='rus+eng', config='--psm 3') # Можно добавить --psm 3 для общего текста
            cleaned_key_text = key_text_raw.strip()

            if not cleaned_key_text:
                key_text_for_dict = f"EMPTY_KEY" # Текст, если ничего не распознано в ключевой области
                cleaned_key_text_for_comparison = ""
            else:
                # Для ключа в словаре делаем текст однострочным и обрезаем для читаемости, если очень длинный
                key_text_for_dict = cleaned_key_text.replace('\n', ' ').replace('\r', ' ').strip()
                if len(key_text_for_dict) > 150:
                    key_text_for_dict = key_text_for_dict[:70] + "..." + key_text_for_dict[-70:] # Обрезаем, но сохраняем начало и конец

                # Для сравнения слов используем полный очищенный текст из ключевой области
                cleaned_key_text_for_comparison = cleaned_key_text 

            print(f"   -> Ключ (текст) распознан: '{key_text_for_dict}'")

        except Exception as e:
            print(f"   -> Ошибка при обработке ключевой области на странице {page_num}: {e}")
            key_text_for_dict = f"ERROR_KEY" # Текст, если произошла ошибка в ключевой области
            cleaned_key_text_for_comparison = "" # Очищаем, чтобы не влияло на список слов
            # Продолжаем, чтобы попробовать обработать остальную часть страницы

        # --- 2. Распознаем весь текст со страницы ---
        cleaned_full_page_text = ""
        try:
            full_page_text_raw = pytesseract.image_to_string(page_image, lang='rus+eng', config='--psm 3')
            cleaned_full_page_text = full_page_text_raw.strip()
            print("   -> Весь текст страницы распознан.")
        except Exception as e:
            print(f"   -> Ошибка при распознавании всей страницы {page_num}: {e}")
            cleaned_full_page_text = ""

        # --- 3. Извлекаем слова из полной страницы и исключаем слова из ключа ---
        all_words_on_page = extract_and_clean_words(cleaned_full_page_text)
        words_in_key_area = set(extract_and_clean_words(cleaned_key_text_for_comparison)) # Используем set для быстрого поиска

        remaining_words = []
        words_added_to_remaining_set = set() # Используем set для отслеживания уникальных слов, которые уже добавлены в remaining_words

        # Проходим по всем словам на странице
        for word in all_words_on_page:
            # Добавляем слово в список, если оно не было в ключевой области
            # И если оно еще не было добавлено в `remaining_words` (чтобы список был из уникальных слов)
            if word not in words_in_key_area and word not in words_added_to_remaining_set:
                remaining_words.append(word)
                words_added_to_remaining_set.add(word)

        # --- 4. Сохраняем результат в словаре с кортежем в качестве ключа ---
        # Ключ теперь будет кортежем: (распознанный_текст_ключа, номер_страницы)
        dictionary_key = (key_text_for_dict, page_num)
        recognized_data_per_page[dictionary_key] = remaining_words

        print(f"   -> Список оставшихся уникальных слов для страницы {page_num} создан (найдено {len(remaining_words)} слов).")

except Exception as e:
    print(f"\nКРИТИЧЕСКАЯ ОШИБКА при обработке PDF: {e}")
    print("Убедитесь, что Tesseract-OCR и Poppler установлены корректно и пути к ним указаны верно.")
    print("Также проверьте, что PDF-файл существует и не поврежден.")


# --- Вывод окончательных результатов в консоль ---
print("\n" + "=" * 60)
print("--- ОКОНЧАТЕЛЬНЫЕ РЕЗУЛЬТАТЫ РАСПОЗНАВАНИЯ В КОНСОЛИ ---")
print("=" * 60)

if recognized_data_per_page:
    # Сортируем по номеру страницы для более удобного просмотра
    sorted_items = sorted(recognized_data_per_page.items(), key=lambda item: item[0][1])

    for key_tuple, value_list in sorted_items:
        key_text_part, page_num_part = key_tuple # Распаковываем кортеж ключа
        print(f"\nКлюч (текст из области) со страницы {page_num_part}: '{key_text_part}'")

        # Выводим только первые N слов для краткости, если список большой
        display_words_limit = 20
        display_words = value_list[:display_words_limit]

        print(f"Оставшиеся уникальные слова на этой странице: {display_words}{'...' if len(value_list) > display_words_limit else ''}")
        print(f"Всего уникальных оставшихся слов на этой странице: {len(value_list)}")
        print("-" * 60)
else:
    print("Результатов распознавания нет. Возможно, PDF пуст, или произошла ошибка во время обработки.")

# --- Сохранение результатов в CSV файл ---
print(f"\nСохранение результатов в CSV файл: '{output_csv_filename}'")
try:
    with open(output_csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        # Используем ',' как стандартный разделитель CSV.
        # quotechar='"' и quoting=csv.QUOTE_MINIMAL позволяют корректно обрабатывать
        # текст с запятыми внутри ячеек.
        csv_writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        # Записываем заголовок
        csv_writer.writerow(['Page Number', 'Key Text', 'Remaining Unique Words'])

        # Записываем данные
        sorted_items = sorted(recognized_data_per_page.items(), key=lambda item: item[0][1])
        for key_tuple, value_list in sorted_items:
            key_text_part, page_num_part = key_tuple

            # Объединяем список оставшихся слов в одну строку с нашим внутренним разделителем
            remaining_words_str = words_internal_delimiter.join(value_list)

            csv_writer.writerow([page_num_part, key_text_part, remaining_words_str])
    print(f"Результаты успешно сохранены в '{output_csv_filename}'.")
except IOError as e:
    print(f"Ошибка при сохранении CSV файла: {e}")

print("\nОбработка завершена.")
