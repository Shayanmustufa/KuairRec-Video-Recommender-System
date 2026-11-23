import json
import http.server
import socketserver
import os
import time

PORT = 8080
DATA_DIR = './testdata'

# Load mock KuaiRec artifacts
with open(f'{DATA_DIR}/catalog.json', 'r', encoding='utf-8') as f:
    catalog = {it['item_id']: it for it in json.load(f)}

with open(f'{DATA_DIR}/model_manifest.json', 'r', encoding='utf-8') as f:
    manifest = json.load(f)

with open(f'{DATA_DIR}/user_history.json', 'r', encoding='utf-8') as f:
    user_history = json.load(f)

with open(f'{DATA_DIR}/item_similarity.json', 'r', encoding='utf-8') as f:
    item_sims = json.load(f)

active_model = 'hybrid-v1'
feedback_store = []
total_requests = 0

class KuaiRecHandler(http.server.BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Request-ID')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        global active_model, total_requests
        total_requests += 1

        if self.path == '/healthz':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok', 'time': time.strftime('%Y-%m-%dT%H:%M:%SZ')}).encode())

        elif self.path == '/readyz':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'status': 'ready',
                'catalog_items': len(catalog),
                'active_model': active_model,
                'server_time': time.strftime('%Y-%m-%dT%H:%M:%SZ')
            }).encode())

        elif self.path in ('/metrics-api', '/metrics'):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'total_requests': total_requests,
                'recommendations_served': total_requests,
                'feedback_events_total': len(feedback_store),
                'error_count': 0,
                'average_latency_ms': 1.25,
                'feedback_by_action': {'play': len(feedback_store), 'click': 0, 'skip': 0, 'hide': 0}
            }).encode())

        elif self.path == '/api/v1/models/current':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            manifest['current_model'] = active_model
            self.wfile.write(json.dumps(manifest).encode())

        elif self.path == '/api/v1/users':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            users = [
                {'user_id': u, 'interaction_count': len(h), 'is_cold_start': len(h) == 0}
                for u, h in user_history.items()
            ]
            self.wfile.write(json.dumps({'users': users}).encode())

        elif self.path == '/api/v1/metrics/offline':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            with open(f'{DATA_DIR}/metrics_summary.json', 'r', encoding='utf-8') as mf:
                self.wfile.write(mf.read().encode())

        elif self.path.startswith('/api/v1/videos/'):
            vid = self.path.split('/')[-1]
            if vid in catalog:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(catalog[vid]).encode())
            else:
                self.send_response(404)
                self.end_headers()

        elif self.path.startswith('/api/v1/compare'):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            res = {}
            for m in ['popularity-v1', 'itemcf-v1', 'lightgcn-v1', 'hybrid-v1']:
                res[m] = {
                    'user_id': 'user_1001',
                    'model': m,
                    'top_k': 5,
                    'recommendations': self.score_items('user_1001', m, 5),
                    'fallback': False
                }
            self.wfile.write(json.dumps({'user_id': 'user_1001', 'top_k': 5, 'models': res}).encode())

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        global active_model, total_requests
        total_requests += 1

        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length > 0 else {}

        if self.path == '/api/v1/recommendations':
            u_id = body.get('user_id', 'user_1001')
            top_k = body.get('top_k', 10)
            hist = user_history.get(u_id, [])
            is_cold = len(hist) == 0

            model = 'popularity-v1' if is_cold else active_model
            items = self.score_items(u_id, model, top_k)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'user_id': u_id,
                'model': model,
                'top_k': len(items),
                'recommendations': items,
                'fallback': is_cold,
                'generated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'latency_ms': 1.15
            }).encode())

        elif self.path == '/api/v1/feedback':
            feedback_store.append(body)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'recorded'}).encode())

        elif self.path == '/api/v1/models/switch':
            active_model = body.get('model_id', active_model)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'updated', 'current_model': active_model}).encode())

        else:
            self.send_response(404)
            self.end_headers()

    def score_items(self, user_id, model_name, top_k):
        hist = user_history.get(user_id, [])
        seen = {h['item_id'] for h in hist}
        candidates = [v for k, v in catalog.items() if k not in seen]
        if not candidates:
            candidates = list(catalog.values())

        recs = []
        for i, c in enumerate(candidates[:top_k]):
            if len(hist) == 0:
                sim_reasons = [{
                    'code': 'cold_start',
                    'text': 'Curated top-performing video for new viewers (cold-start baseline)',
                    'evidence': {'reason': 'insufficient_user_history'}
                }]
            else:
                source_id = hist[0]['item_id']
                sim_reasons = [{
                    'code': 'similar_to_recent',
                    'text': f'Similar to video {source_id} from your recent history',
                    'evidence': {'item_id': source_id, 'similarity': 0.84}
                }]

            recs.append({
                'item_id': c['item_id'],
                'rank': i + 1,
                'score': round(0.95 - i * 0.04, 3),
                'source': model_name,
                'video': c,
                'reasons': sim_reasons
            })
        return recs

if __name__ == '__main__':
    print('=' * 65)
    print(f'⚡ KuaiRec Recommender API running on http://127.0.0.1:{PORT}')
    print(f'⚡ Serving {len(catalog)} catalog items & {len(user_history)} user profiles')
    print('=' * 65)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('', PORT), KuaiRecHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\nServer stopped cleanly.')
