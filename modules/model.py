from transformers import pipeline
import torch
import re


def load_model(base_dir=None):
    """Load a pre-trained NER model from Hugging Face"""
    try:
        # Use a reliable pre-trained English NER model
        pipe = pipeline(
            "ner",
            model="dslim/bert-base-NER",
            aggregation_strategy="simple",
            device=0 if torch.cuda.is_available() else -1
        )
        return pipe
    except Exception as e:
        raise Exception(f"Failed to load pipeline: {e}")

def detect_pii_regex(text):
    """Detect PII using regex patterns"""
    patterns = {
        "I-EMAIL": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "I-TELEPHONENUM": r'\+?\d{1,4}?[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{3,5}[-.\s]?\d{3,5}(?:[-.\s]?\d{1,6})?',
        "I-SOCIALNUM": r'\b\d{3}-\d{2}-\d{4}\b',
        "I-CREDITCARDNUMBER": r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        "I-ZIPCODE": r'\b\d{5}(?:-\d{4})?\b',
        "I-DATEOFBIRTH": r'\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b|\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',
    }
    
    results = []
    for label, pattern in patterns.items():
        for match in re.finditer(pattern, text):
            results.append({
                'entity': label,
                'score': 1.0,
                'start': match.start(),
                'end': match.end(),
                'word': match.group()
            })
    
    return results

def mask_text(pipe, text):
    from modules.redaction import apply_redaction
    
    # Get NER predictions with safe processing
    ner_predictions = []
    try:
        # Safe processing for long texts
        max_chunk_size = 500  # Reduced chunk size to avoid meta tensor issues
        if len(text) <= max_chunk_size:
            try:
                ner_predictions = pipe(text)
            except Exception as e:
                ner_predictions = []
        else:
            # Process in chunks with overlap to catch entities at boundaries
            chunks = []
            overlap = 50  # Overlap between chunks
            for i in range(0, len(text), max_chunk_size - overlap):
                chunk_end = min(i + max_chunk_size, len(text))
                chunks.append((i, text[i:chunk_end]))
            
            for offset, chunk in chunks:
                try:
                    # Process chunk
                    chunk_predictions = pipe(chunk)
                    # Adjust start/end positions for the full text
                    for pred in chunk_predictions:
                        pred['start'] = pred.get('start', 0) + offset
                        pred['end'] = pred.get('end', 0) + offset
                    ner_predictions.extend(chunk_predictions)
                except RuntimeError as e:
                    if "meta tensors" in str(e):
                        continue
                except Exception as e:
                    pass
    except Exception as e:
        pass
    
    # Convert NER predictions to our expected format
    converted_predictions = []
    for pred in ner_predictions:
        entity = pred.get('entity_group', pred.get('entity', 'O'))
        
        # Remove B- or I- prefixes if present
        if entity.startswith('B-') or entity.startswith('I-'):
            entity = entity[2:]
        
        # Map standard NER labels to PII types
        label_mapping = {
            'PER': 'I-GIVENNAME',
            'PERSON': 'I-GIVENNAME',
            'LOC': 'I-CITY',
            'LOCATION': 'I-CITY',
            'ORG': 'I-USERNAME',
            'ORGANIZATION': 'I-USERNAME',
            'MISC': 'I-USERNAME'
        }
        
        mapped_entity = label_mapping.get(entity, f'I-{entity}' if entity != 'O' else 'O')
        
        converted_predictions.append({
            'entity': mapped_entity,
            'score': pred.get('score', 1.0),
            'start': pred.get('start', 0),
            'end': pred.get('end', 0),
            'word': pred.get('word', ''),
            'index': len(converted_predictions)
        })
    
    # Add regex-based PII detection
    regex_predictions = detect_pii_regex(text)
    converted_predictions.extend(regex_predictions)
    
    # Sort by start position to avoid conflicts
    converted_predictions.sort(key=lambda x: x['start'])
    
    # Remove overlapping predictions (keep higher confidence ones)
    final_predictions = []
    for pred in converted_predictions:
        overlap = False
        for existing in final_predictions[:]:  # Use slice to avoid modification during iteration
            if (pred['start'] < existing['end'] and pred['end'] > existing['start']):
                if pred['score'] <= existing.get('score', 0):
                    overlap = True
                    break
                else:
                    final_predictions.remove(existing)
        if not overlap:
            final_predictions.append(pred)
    
    # Apply redaction to all detected PII
    redacted_text = apply_redaction(text, final_predictions)
    return redacted_text