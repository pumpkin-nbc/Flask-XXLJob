"""适合 Python 初学者的最小可运行示例。 / Minimal runnable beginner example."""

from __future__ import annotations

from flask import Flask, jsonify

from flask_xxljob import FlaskXXLJob, XXLJobResponse

app = Flask(__name__)

# 第一阶段只在本机验证，不连接 XXL-JOB Admin。
# Stage one is local-only and does not connect to XXL-JOB Admin.
app.config.update(
    XXL_JOB_AUTO_REGISTER=False,
    XXL_JOB_ROUTE_PREFIX="/xxl-job",
)

xxl_job = FlaskXXLJob(app)


@app.route("/", methods=["GET"])
def index():
    return jsonify(
        message="Flask-XXLJob beginner example is running",
        beat="POST /xxl-job/beat",
        run="POST /xxl-job/run",
    )


@xxl_job.on_run
def handle_run(request):
    """接收任务；这里只打印参数，方便先看懂流程。 / Print the received task."""
    print("收到任务 / Received job")
    print("job_id:", request.job_id)
    print("handler:", request.executor_handler)
    print("params:", request.parse_params())
    return XXLJobResponse.success(content="任务已收到 / job received")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)
