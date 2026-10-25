def truncate(text, max_len):
    if len(text) >= max_len:
        return text[:max_len] + "..."
    return text


def capitalize_words(text):
    return " ".join(word.capitalize() for word in text.split())


def reverse_words(text):
    return " ".join(text.split()[::-1])
