import bcrypt


def hash_password(password: str) -> str:
    """ 对密码加密并返回加密后的字符串 """
    if len(password.encode("utf-8")) > 72:
        raise ValueError("密码 UTF-8 编码长度不得超过 72 字节")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, hashed_password: str) -> bool:
    """ 验证密码是否与加密后的字符串匹配 """
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False
