def merge_predictions(predictions):
    if not predictions:
        return []
    merged = []
    
    # Filter out predictions that don't have required keys
    valid_predictions = []
    for pred in predictions:
        try:
            # Ensure prediction has required keys
            entity = pred.get('entity_group', pred.get('entity', 'O'))
            start = pred.get('start', 0)
            end = pred.get('end', 0)
            
            # Create normalized prediction
            normalized_pred = {
                'entity': entity,
                'start': start,
                'end': end,
                'score': pred.get('score', 1.0),
                'word': pred.get('word', '')
            }
            valid_predictions.append(normalized_pred)
        except (KeyError, AttributeError, TypeError) as e:
            continue
    
    if not valid_predictions:
        return []
    
    current = dict(valid_predictions[0])
    for pred in valid_predictions[1:]:
        if (pred['start'] == current['end'] and pred['entity'] == current['entity'] and pred['entity'] != 'O'):
            current['end'] = pred['end']
        else:
            merged.append(current)
            current = dict(pred)
    merged.append(current)
    return merged