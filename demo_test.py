"""
Slopsquatting Detector 시연용 테스트 파일

3가지 케이스:
1. 정상 패키지 (LOW)     → flask, numpy, pandas
2. 오타 패키지 (MEDIUM)  → flsk, nunpy, panadas
3. 가짜 패키지 (CRITICAL) → fastapi-redis-rbac-bouncer, neural_optim_magic
"""

# ── 정상 패키지 ──────────────────────────────
import flask
import numpy as np
import pandas as pd
from requests import get

# ── 오타 패키지 ──────────────────────────────
import flsk              # flask의 오타
import nunpy             # numpy의 오타
from tensorfloww import keras  # tensorflow의 오타

# ── 환각/가짜 패키지 ─────────────────────────
import fastapi_redis_rbac_bouncer  # 존재하지 않는 패키지
from neural_optim_magic import Optimizer  # AI 환각 패키지
import auto_ml_accelerator_pro  # 존재하지 않는 패키지


def main():
    app = flask.Flask(__name__)

    @app.route("/")
    def index():
        return "Hello, World!"

    app.run(debug=True)


if __name__ == "__main__":
    main()
