from datetime import datetime, timezone
from models.user import UserModel

async def create_user_if_not_exists(mobileNo: str):
    print(mobileNo)
    # Check if exists
    existing_user = await UserModel.find_one(UserModel.mobileNo == mobileNo)

    if existing_user:
        # Update last_used instead (optional behavior)
        existing_user.last_used = datetime.now(timezone.utc)
        await existing_user.save()
        return existing_user

    # Insert new user
    user = UserModel(
        mobileNo=mobileNo,
        last_used=datetime.now(timezone.utc)
    )

    return await user.insert()
