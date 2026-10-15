import json
import os
import config

def save_event(filename, event_data):
    """
    Guarda un objeto JSON en una nueva línea del archivo especificado.
    """
    filepath = os.path.join(config.OUTPUT_DIR, filename)
    with open(filepath, 'a', encoding='utf-8') as f:
        # ensure_ascii=False garantiza que se guarde en UTF-8 correcto
        f.write(json.dumps(event_data, ensure_ascii=False) + '\n')