def _get_part_text(text: str, start: int, page_size: int) -> list:
    
    text_1 = text[start: page_size + start + 1]
    for i in range(len(text_1)):
        text_2 = text_1[-2: ]
        if  text_2 in ('. ', ', ', '! ', ': ', '; ', '? '):
            return [text_1, len(text_1)-1]
        else:
            text_1 = text_1[ :-1]
    return ['']


text = 'Раз. Два. Три. Четыре. Пять. Прием!'

print(*_get_part_text(text, 5, 9), sep='\n')

