from flask import Flask, Response, request, jsonify
from curl_cffi import requests as async_requests
import os
import re

app = Flask(__name__)

# Jo cookies tune di hain, unko yahan permanent store kiya hai
RARE_STUDY_COOKIES = (
    "Session_expiry=1794367353227; "
    "cf_clearance=CuoPngFCChi1vIhjbxzJsrCLEBxqIiJ-SlUorAr5tyi4Rzwsj6VV9M6-QBpGMPO4_9Ji-q5LbYsfTmTWxvVgkwKRQPpgwfnjPuo7flajMjRMsK-mrf29qW7IFzHboawQnco-qT4HJCnRm0fBLpBU_ZqdbI2ROB0cr-FWtrWoHq9Z0_MU5zpXFK7C854_cB0BTGdlVdLABUSdAY_63HUUxLJQaZTJ_-W5FXrTvRdzCywWCWNjg4If34U7HVvyL1HcXtpI-MQmORWZ65nT9hn4ylGWMy_xpRZ46IQ8zZAApGPhnYkN7eFLm0GYzbd1TVuQDJE2F8E; "
    "session=.eJwFwdtugjAAANB_6fNMhAJhvo2KoNzUwgBfSCN0oLYF2rLpsn_fOb-gGbuZEd5xBTZq1t0bmGUjOykHwcEGLMmS-0ffCl7TDltXgbUQdbE-LPbnlwEpDMNn-eHIuhdegOPpweLtOx2u9jgeLmWNac_WmTs0HTySSUXxODkoNezIMrda72i71xz9nHh2S88JgrKdi8C30lNOTWFXE7z3grTfyh0HzCrnlYfUw1Xc3pp9krOzjh69q4sy4MZl9UT5QrRWsFwVJLMCikvu6fg7x_bP02U.avM2Cg.CsFFEaB9DLcCbiE3XHpSoe7WsA8"
)

@app.route('/proxy', methods=['GET'])
def proxy_stream():
    target_url = request.args.get('url')
    
    if not target_url:
        return jsonify({"success": False, "error": "Missing target 'url' parameter"}), 400

    # Rare Study ke official headers + Cookies
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://rarestudy.testuk.org/",
        "Origin": "https://rarestudy.testuk.org",
        "Cookie": RARE_STUDY_COOKIES,
        "Accept": "*/*"
    }

    try:
        # Request target CDN/server
        res = async_requests.get(target_url, headers=headers, impersonate="chrome120", timeout=25)
        
        content_type = res.headers.get('Content-Type', '')
        content_bytes = res.content

        # Agar yeh manifest file (.mdp ya .m3u8) hai, toh andar ke links rewrite kar do
        if '.mdp' in target_url or '.m3u8' in target_url or 'application' in content_type:
            text_content = content_bytes.decode('utf-8', errors='ignore')
            
            # Base URL nikalne ke liye taaki relative links ko absolute banaya ja sake
            base_url = target_url.rsplit('/', 1)[0]

            def rewrite_link(match):
                original_link = match.group(1)
                # Agar link relative hai, toh use absolute banao
                if not original_link.startswith('http'):
                    absolute_link = f"{base_url}/{original_link}"
                else:
                    absolute_link = original_link
                
                # Heroku proxy ka khud ka route bana do har segment ke liye
                heroku_host = request.host_url.rstrip('/')
                return f'="{heroku_host}/proxy?url={absolute_link}"'

            # M3U8 ya DASH manifest ke andar ke URLs ko regex se pakad kar rewrite karna
            # (Matches URLs inside quotes or tags)
            rewritten_content = re.sub(r'["\'](?!http)([^"\']+\.(ts|m4s|m3u8|mp4|key)[^"\']*)["\']', rewrite_link, text_content)
            # Catch absolute links inside manifests too
            rewritten_content = re.sub(r'["\'](https?://[^"\']+\.(ts|m4s|m3u8|mp4|key)[^"\']*)["\']', lambda m: f'="{request.host_url.rstrip("/")}/proxy?url={m.group(1)}"', rewritten_content)

            return Response(rewritten_content, status=res.status_code, content_type=content_type or 'application/vnd.apple.mpegurl')

        # Agar normal video segment (.ts/.m4s) ya koi aur file hai, toh seedha binary stream bhej do
        return Response(content_bytes, status=res.status_code, content_type=content_type or 'video/mp2t')
            
    except Exception as err:
        return jsonify({
            "success": False,
            "error": str(err),
            "message": "Failed to stream content via proxy."
        }), 500

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "online",
        "message": "Full Streaming Proxy & Manifest Rewriter Active",
        "poweredBy": "Next Study"
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
  
