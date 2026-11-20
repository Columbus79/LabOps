from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest
from app.models.user import User
from app.utils.password import verify_password, hash_password
from app.common.exceptions import BusinessException
from app.utils.jwt import create_access_token
from app.schemas.user import UserResponse
from app.common.response import Response


def login(db: Session, data: LoginRequest):
    # 根据用户账号查询数据库
    user = db.query(User).filter(User.username == data.username).first()

    # 判断账号和密码是否正确
    if not user or not verify_password(data.password, user.password):
        raise BusinessException(message="账号或密码错误")
    # 验证账号状态
    if user.status != 1:
        raise BusinessException(message="账号已经被禁用")
    # 创建token
    token = create_access_token(user_id=user.id)

    return LoginResponse(
        token=token,
        user=UserResponse.model_validate(user).model_dump(),
    )
    # model_validate()：我要拿着()内的数据然后根据前面的模型类规则创建一个符合特定规则的 Pydantic 对象。
    # model_dump()：我现在不想继续使用这个 Pydantic 对象，而是想把它的数据拿出来，得到一个普通字典。


def register(db: Session, data: RegisterRequest):
    # 根据用户账号查询数据库
    user = db.query(User).filter(User.username == data.username).first()
    if user:
        raise BusinessException(message="账号已存在")
    user_model = User(
        username=data.username,
        
        password=hash_password(data.password),
        name=data.name or data.username,
        role="student",
        status=1,
    )
    try:
        db.add(user_model)
        db.commit()
        db.refresh(user_model)
    except IntegrityError as exc:
        db.rollback()
        if db.query(User.id).filter(User.username == data.username).first():
            raise BusinessException(message="账号已存在", code=409) from exc
        raise
