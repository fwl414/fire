from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

print('=== 登录失败次数限制测试 ===')
print()

for i in range(1, 7):
    r = client.post('/api/auth/login', data={'username': 'admin', 'password': 'wrongpassword'})
    msg = r.json().get('message', '')
    print(f'第{i}次失败: {msg}')
    if '锁定' in msg:
        print(f'  ✓ 第{i}次触发锁定')
        break

print()
r = client.post('/api/auth/login', data={'username': 'admin', 'password': '123456'})
res = r.json()
print(f'锁定后用正确密码登录: {r.status_code} - {res.get("message", "")}')
assert r.status_code == 401
print('  ✓ 锁定后正确密码也无法登录')

print()
print('登录失败限制功能正常!')
