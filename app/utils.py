def html_to_markdown(tag_name: str, text: str) -> str:
    """
    Convert HTML elements to their markdown equivalents
    """
    markdown_mappings = {
        "h1": f"# {text}",
        "h2": f"## {text}",
        "h3": f"### {text}",
        "h4": f"#### {text}",
        "h5": f"##### {text}",
        "h6": f"###### {text}",
        "p": text,
        "strong": f"**{text}**",
        "b": f"**{text}**",
        "em": f"*{text}*",
        "i": f"*{text}*",
        "code": f"`{text}`",
        "pre": f"```\n{text}\n```",
        "blockquote": f"> {text}",
        "li": f"- {text}",
        "a": lambda text, href: f"[{text}]({href})",
        "hr": "---",
        "del": f"~~{text}~~",
        "sup": f"^{text}^",
        "sub": f"~{text}~",
    }

    return markdown_mappings.get(tag_name.lower(), text)
