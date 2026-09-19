# TLS 证书部署说明

前端容器（nginx）以 HTTPS 作为唯一对外入口，证书从宿主机目录 `./certs` 只读挂载：

| 容器内路径 | 宿主机路径 | 说明 |
| --- | --- | --- |
| `/etc/nginx/certs/fullchain.pem` | `./certs/fullchain.pem` | 站点证书（含中间 CA 的完整链） |
| `/etc/nginx/certs/privkey.pem` | `./certs/privkey.pem` | 证书私钥（无口令、PKCS#8 PEM） |
| `/var/www/certbot` | `./certs/www` | Let's Encrypt http-01 校验目录（webroot） |

两个文件缺任意一个，`frontend` 容器都会启动失败（nginx 读取证书报错），
因此**首次部署必须先准备好证书**。`certs/` 已在 `.gitignore` 中，私钥不会入库。

---

## 方式一：Let's Encrypt 自动签发（有公网域名）

前提：域名 A 记录已指向本机，且 80 / 443 可从公网访问。

**第 1 步：先放一张自签证书，让 nginx 能起来**

Let's Encrypt 的 http-01 校验要靠 nginx 的 80 端口提供 `/.well-known/acme-challenge/`，
而 nginx 没有证书又起不来，所以先用自签证书过渡：

```bash
mkdir -p certs/www
openssl req -x509 -nodes -newkey rsa:2048 -days 90 \
  -keyout certs/privkey.pem -out certs/fullchain.pem \
  -subj "/CN=your.domain.com"
docker compose up -d frontend
```

**第 2 步：申请正式证书（webroot 模式，不影响已运行的 nginx）**

```bash
docker run --rm \
  -v fire_ai_letsencrypt:/etc/letsencrypt \
  -v "$PWD/certs/www:/var/www/certbot" \
  certbot/certbot certonly --webroot -w /var/www/certbot \
  -d your.domain.com --email admin@your.domain.com --agree-tos --no-eff-email
```

**第 3 步：把证书拷到 `./certs` 并热加载 nginx**

```bash
docker run --rm \
  -v fire_ai_letsencrypt:/etc/letsencrypt \
  -v "$PWD/certs:/out" \
  alpine sh -c "cp /etc/letsencrypt/live/your.domain.com/fullchain.pem /out/ && \
                cp /etc/letsencrypt/live/your.domain.com/privkey.pem /out/"
docker compose exec frontend nginx -s reload
```

**第 4 步：续期**

Let's Encrypt 证书有效期 90 天。建议在宿主机加一条 cron（每周一 03:30 尝试续期）：

```
30 3 * * 1 cd /path/to/project && docker run --rm -v fire_ai_letsencrypt:/etc/letsencrypt -v "$PWD/certs/www:/var/www/certbot" certbot/certbot renew --quiet && docker run --rm -v fire_ai_letsencrypt:/etc/letsencrypt -v "$PWD/certs:/out" alpine sh -c "cp /etc/letsencrypt/live/your.domain.com/*.pem /out/" && docker compose exec frontend nginx -s reload
```

---

## 方式二：使用机构签发的证书（商业 CA / 内网 CA）

无需 ACME 校验，直接把签发结果重命名放入 `./certs`：

```
certs/fullchain.pem   # 站点证书 + 中间 CA（按证书链顺序拼接）
certs/privkey.pem     # 与站点证书配对的私钥
certs/www/            # 目录可留空，仅 Let's Encrypt 场景需要
```

放好后 `docker compose up -d frontend`，再 `docker compose exec frontend nginx -s reload`（已运行时）。

---

## 常见问题

- **私钥有口令**：nginx 启动会交互式要口令而挂起，必须转成无口令 PEM：
  `openssl rsa -in enc.key -out certs/privkey.pem`
- **证书链不完整**：只放站点证书会导致部分客户端（尤其移动端）报 `unable to get local issuer certificate`，
  `fullchain.pem` 必须是「站点证书 + 中间 CA」的拼接。
- **域名与证书不匹配**：`nginx.conf` 的 `server_name` 保持默认 `localhost` 不影响访问（它是默认 server），
  但 HSTS 一旦下发到浏览器会被记住一年，**首次切正式域名前建议先用测试域名验证**，别在正式域名上试错。
- **想临时关闭 HTTPS**：把 `nginx.conf` 里的 443 server 与 80 的 `return 301` 去掉，
  或直接不映射 443 端口，仅保留 `HTTP_PORT=80`（不推荐，生产应始终走 HTTPS）。

## 验证

```bash
# 握手与证书链
openssl s_client -connect your.domain.com:443 -servername your.domain.com </dev/null | openssl x509 -noout -subject -dates

# 跳转与 HSTS 头
curl -sI http://your.domain.com/health        # 期望 301 到 https
curl -sI https://your.domain.com/health       # 期望 200 且含 Strict-Transport-Security
```
