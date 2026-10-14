from urllib.parse import urlsplit

ALLOW = {'allow','allow once','allow this time','approve','approve once','yes','允许','允许一次','仅允许这一次','批准','同意','是'}
DENY = {'deny','reject','decline','cancel','no','拒绝','不允许','取消','否'}

def provider(url):
    try:
        u = urlsplit(url)
        if u.username is not None or u.password is not None or u.port is not None:
            return None
        if u.scheme == 'https':
            if u.path.startswith(('/artifact', '/share', '/public')): return None
            return {'chatgpt.com':'gpt', 'chat.openai.com':'gpt', 'claude.ai':'claude', 'chat.deepseek.com':'deepseek'}.get(u.hostname)
        if u.scheme == 'chrome-extension':
            return {'hehggadaopoacecdllhhajmbjkdcmajg':'gpt','fcoeoabgfenejglbffodgkkbkcdhcgfn':'claude'}.get(u.hostname)
    except ValueError:
        pass
    return None

def decision(label):
    text = label.strip().lower()
    return True if text in ALLOW else False if text in DENY else None

def is_request(text, buttons):
    if (len(text.encode()) >= 60000 or len(text) <= 8 or not 2 <= len(buttons) <= 6 or len(set(buttons)) != len(buttons)
        or not any(decision(b) is True for b in buttons) or not any(decision(b) is False for b in buttons)):
        return False
    return any(word in text.lower() for word in ['approval','permission','allow','approve','run this command','execute','申请','批准','权限','允许','执行','授权'])
