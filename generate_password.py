import streamlit_authenticator as stauth

def generate_password_hash(password):
    """비밀번호의 해시를 생성합니다."""
    return stauth.Hasher([password]).generate()[0]

if __name__ == "__main__":
    # 사용할 비밀번호들
    passwords = ['admin123', 'user123', 'user456', 'password123']
    
    print("=== 비밀번호 해시 생성 결과 ===")
    for password in passwords:
        hashed = generate_password_hash(password)
        print(f"원본: {password} -> 해시: {hashed}")
    
    print("\n=== config.yaml에 사용할 형식 ===")
    print("credentials:")
    print("  usernames:")
    for i, password in enumerate(passwords, 1):
        hashed = generate_password_hash(password)
        print(f"    user{i}:")
        print(f"      email: user{i}@company.com")
        print(f"      name: 사용자{i}")
        print(f"      password: {hashed}") 