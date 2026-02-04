import os
import subprocess
import base64
import tarfile
import io
import json
import tempfile
import threading
from fastmcp import FastMCP
from fastapi import FastAPI
from fastapi.responses import FileResponse
import uvicorn

# 创建MCP服务器实例
mcp = FastMCP("skill-manager")

# 创建FastAPI应用
fastapi_app = FastAPI()

# 配置
REPO_URL = "git@coding.jd.com:jdi-qygyl/ai-efficiency-skills.git"
LOCAL_DIR = "/opt/projects/python/mcp_test/ai-efficiency-skills"
CACHE_DIR = os.path.join(LOCAL_DIR, ".skill-cache")  # 压缩包缓存目录
SKILL_FILE_BASE_URL = "http://localhost:8002"

# 全局skills变量
skills = {}


def run_command(cmd: list, cwd: str = None):
    """执行 shell 命令，返回 (returncode, stdout, stderr)"""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        raise Exception("Command timeout")
    except Exception as e:
        raise Exception(f"Command error: {str(e)}")


def update_skills():
    """遍历LOCAL_DIR下的一级文件夹，读取skill.md文件并更新skills变量"""
    global skills
    skills = {}

    if not os.path.exists(LOCAL_DIR):
        return

    # 遍历LOCAL_DIR下的所有一级文件夹
    for folder_name in os.listdir(LOCAL_DIR):
        folder_path = os.path.join(LOCAL_DIR, folder_name)

        # 只处理文件夹
        if not os.path.isdir(folder_path):
            continue

        # 查找skill.md文件（忽略大小写）
        skill_md_path = None
        for file_name in os.listdir(folder_path):
            if file_name.lower() == 'skill.md':
                skill_md_path = os.path.join(folder_path, file_name)
                break

        # 如果不存在skill.md文件，跳过
        if not skill_md_path:
            continue

        # 读取skill.md文件的前6行
        try:
            with open(skill_md_path, 'r', encoding='utf-8') as f:
                lines = [f.readline() for _ in range(6)]

            # 从前5行中提取name和description
            name = None
            description = None
            for line in lines[:5]:
                line = line.strip()
                if line.startswith('name:'):
                    name = line.split('name:', 1)[1].strip()
                elif line.startswith('description:'):
                    description = line.split('description:', 1)[1].strip()

            # 存储到skills字典中
            skills[folder_name] = {
                'folder_name': folder_name,
                'name': name,
                'description': description
            }
        except Exception as e:
            print(f"Error reading skill.md in {folder_name}: {e}")
            continue


def clear_cache():
    """清理压缩包缓存"""
    if os.path.exists(CACHE_DIR):
        import shutil
        shutil.rmtree(CACHE_DIR)
        print("🗑️  已清理压缩包缓存")


def sync_repo_internal():
    """内部同步仓库函数"""
    if os.path.exists(LOCAL_DIR):
        # 已存在，执行 git pull
        code, out, err = run_command(["git", "pull"], cwd=LOCAL_DIR)
        if code != 0:
            raise Exception(f"Git pull failed: {err}")

        # 只有当不是"Already up to date"时才更新skills和清理缓存
        if "Already up to date" not in out:
            update_skills()
            clear_cache()  # 清理缓存，下次下载会重新生成
        else:
            update_skills()

        return {"status": "updated", "message": "Repository updated successfully"}
    else:
        # 不存在，执行 git clone
        parent_dir = os.path.dirname(LOCAL_DIR)
        repo_name = os.path.basename(LOCAL_DIR)
        code, out, err = run_command(["git", "clone", REPO_URL, repo_name], cwd=parent_dir)
        if code != 0:
            raise Exception(f"Git clone failed: {err}")

        # clone后更新skills
        update_skills()

        return {"status": "cloned", "message": "Repository cloned successfully"}


# @mcp.tool()
def sync_repo() -> dict:
    """
    同步技能仓库，执行git clone或git pull操作。
    如果本地仓库不存在则clone，存在则pull最新代码。

    Returns:
        dict: 包含同步状态和消息的字典
    """
    try:
        return sync_repo_internal()
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def list_skills(keyword: str = "") -> dict:
    """
    列出所有可用的技能。支持关键词搜索。

    Args:
        keyword: 搜索关键词（可选），匹配 name 或 description

    Returns:
        dict: 技能列表，包含 id、name、description 等信息
    """
    try:
        sync_repo_internal()

        results = {}
        for skill_id, info in skills.items():
            # 关键词过滤
            if keyword:
                keyword_lower = keyword.lower()
                name = (info.get('name') or '').lower()
                desc = (info.get('description') or '').lower()

                if keyword_lower not in name and keyword_lower not in desc:
                    continue

            results[skill_id] = info

        return {
            "status": "success",
            "count": len(results),
            "data": results
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def get_skill_info(skill_id: str) -> dict:
    """
    获取单个技能的详细信息。

    Args:
        skill_id: 技能 ID

    Returns:
        dict: 技能详细信息，包括文件数量、大小等
    """
    try:
        sync_repo_internal()

        if skill_id not in skills:
            return {"status": "error", "message": f"Skill '{skill_id}' not found"}

        skill_info = skills[skill_id].copy()
        skill_path = os.path.join(LOCAL_DIR, skill_id)

        # 统计文件信息
        file_count = 0
        total_size = 0
        for root, dirs, files in os.walk(skill_path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            file_count += len(files)
            for f in files:
                try:
                    total_size += os.path.getsize(os.path.join(root, f))
                except:
                    pass

        skill_info['file_count'] = file_count
        skill_info['total_size_bytes'] = total_size
        skill_info['total_size_kb'] = round(total_size / 1024, 2)

        return {"status": "success", "data": skill_info}

    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def clear_skill_cache() -> dict:
    """
    清理技能压缩包缓存。
    当仓库更新后，可以手动清理缓存以强制重新生成压缩包。

    Returns:
        dict: 清理结果
    """
    try:
        if os.path.exists(CACHE_DIR):
            import shutil
            shutil.rmtree(CACHE_DIR)
            return {"status": "success", "message": "压缩包缓存已清理"}
        else:
            return {"status": "success", "message": "缓存目录不存在，无需清理"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def download_skill(skill_id: str = "", download_all: bool = False, install_dir: str = "") -> dict:
    """
    获取技能下载信息。

    返回 HTTP 下载 URL，客户端使用 curl 命令下载并解压：
    - 使用 -k 参数解压时跳过已存在的文件
    - 压缩包存在则覆盖

    Args:
        skill_id: 技能 ID（如果 download_all=True 则忽略此参数）
        download_all: 是否下载所有技能（默认 False）
        install_dir: 安装目录（默认为 ~/.claude/skills）

    Returns:
        dict: 包含 download_url 的下载信息
    """
    try:
        sync_repo_internal()

        # 确定安装目录
        target_dir = install_dir if install_dir else "~/.claude/skills"

        if download_all:
            # 下载所有技能
            return {
                "status": "success",
                "skill_id": "all",
                "count": len(skills),
                "download_url": f"${SKILL_FILE_BASE_URL}/download/all",
                "install_dir": target_dir,
                "instruction": f"mkdir -p {target_dir} && curl -o {target_dir}/all-skills.tar.gz ${SKILL_FILE_BASE_URL}/download/all && tar -xkzf {target_dir}/all-skills.tar.gz -C {target_dir}/ && rm {target_dir}/all-skills.tar.gz"
            }
        else:
            # 下载单个技能
            if not skill_id:
                return {"status": "error", "message": "请指定 skill_id 或设置 download_all=true"}

            if skill_id not in skills:
                return {"status": "error", "message": f"Skill '{skill_id}' not found"}

            skill_path = os.path.join(LOCAL_DIR, skill_id)

            if not os.path.exists(skill_path):
                return {"status": "error", "message": f"Skill path does not exist: {skill_path}"}

            # 计算大小
            total_size = 0
            for root, dirs, files in os.walk(skill_path):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in files:
                    try:
                        total_size += os.path.getsize(os.path.join(root, f))
                    except:
                        pass

            return {
                "status": "success",
                "skill_id": skill_id,
                "download_url": f"${SKILL_FILE_BASE_URL}/download/{skill_id}",
                "size_kb": round(total_size / 1024, 2),
                "install_dir": target_dir,
                "instruction": f"mkdir -p {target_dir} && curl -o {target_dir}/{skill_id}.tar.gz ${SKILL_FILE_BASE_URL}/download/{skill_id} && tar -xkzf {target_dir}/{skill_id}.tar.gz -C {target_dir}/ && rm {target_dir}/{skill_id}.tar.gz"
            }

    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.resource("skills://list")
def get_skills_list() -> str:
    """
    获取所有技能列表（元数据）。
    返回 JSON 格式的技能列表，不包含文件内容。
    """
    try:
        sync_repo_internal()
        result = {
            "status": "success",
            "message": "技能列表",
            "data": skills
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e),
            "data": {}
        }, ensure_ascii=False)


@mcp.resource("skills://{skill_id}")
def get_skill_detail(skill_id: str) -> str:
    """
    获取单个技能的详细元数据。
    返回 JSON 格式，不包含文件内容。
    """
    try:
        sync_repo_internal()

        if skill_id not in skills:
            return json.dumps({
                "status": "error",
                "message": f"Skill '{skill_id}' not found"
            }, ensure_ascii=False)

        skill_info = skills[skill_id].copy()

        # 添加额外信息
        skill_path = os.path.join(LOCAL_DIR, skill_id)

        # 统计文件信息
        file_count = 0
        total_size = 0
        for root, dirs, files in os.walk(skill_path):
            # 跳过 .git 等隐藏目录
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            file_count += len(files)
            for f in files:
                try:
                    total_size += os.path.getsize(os.path.join(root, f))
                except:
                    pass

        skill_info['file_count'] = file_count
        skill_info['total_size_bytes'] = total_size
        skill_info['total_size_kb'] = round(total_size / 1024, 2)
        skill_info['download_uri'] = f"skills://{skill_id}/download"

        return json.dumps({
            "status": "success",
            "data": skill_info
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e)
        }, ensure_ascii=False)


@mcp.resource("skills://{skill_id}/download")
def download_skill_resource(skill_id: str) -> str:
    """
    下载完整的技能目录（压缩包）。
    返回 base64 编码的 tar.gz 文件。

    客户端收到此数据后应：
    1. 保存压缩包到当前项目目录下即可
    """
    try:
        sync_repo_internal()

        # 特殊处理：下载所有技能
        if skill_id == "all":
            tar_buffer = io.BytesIO()
            with tarfile.open(fileobj=tar_buffer, mode='w:gz') as tar:
                for sid in skills.keys():
                    skill_path = os.path.join(LOCAL_DIR, sid)
                    if os.path.exists(skill_path):
                        tar.add(skill_path, arcname=sid)

            tar_buffer.seek(0)
            encoded = base64.b64encode(tar_buffer.read()).decode('utf-8')
            return encoded

        # 下载单个技能
        if skill_id not in skills:
            raise Exception(f"Skill '{skill_id}' not found")

        skill_path = os.path.join(LOCAL_DIR, skill_id)

        if not os.path.exists(skill_path):
            raise Exception(f"Skill path does not exist: {skill_path}")

        # 创建内存中的 tar.gz
        tar_buffer = io.BytesIO()

        with tarfile.open(fileobj=tar_buffer, mode='w:gz') as tar:
            tar.add(skill_path, arcname=skill_id)

        # 返回 base64 编码
        tar_buffer.seek(0)
        encoded = base64.b64encode(tar_buffer.read()).decode('utf-8')

        return encoded

    except Exception as e:
        # 错误时返回 JSON 格式的错误信息
        return json.dumps({
            "status": "error",
            "message": str(e)
        }, ensure_ascii=False)


# FastAPI 下载端点
@fastapi_app.get("/download/{skill_id}")
async def download_skill_http(skill_id: str):
    """
    通过 HTTP 下载技能压缩包
    先检查缓存目录是否存在压缩包，不存在则创建
    """
    try:
        sync_repo_internal()

        # 确保缓存目录存在
        os.makedirs(CACHE_DIR, exist_ok=True)

        # 特殊处理：下载所有技能
        if skill_id == "all":
            cache_file_path = os.path.join(CACHE_DIR, "all-skills.tar.gz")

            # 检查缓存是否存在
            if not os.path.exists(cache_file_path):
                # 不存在则创建压缩包
                with tarfile.open(cache_file_path, mode='w:gz') as tar:
                    for sid in skills.keys():
                        skill_path = os.path.join(LOCAL_DIR, sid)
                        if os.path.exists(skill_path):
                            tar.add(skill_path, arcname=sid)

            return FileResponse(
                cache_file_path,
                media_type='application/gzip',
                filename='all-skills.tar.gz'
            )

        # 下载单个技能
        if skill_id not in skills:
            return {"status": "error", "message": f"Skill '{skill_id}' not found"}

        skill_path = os.path.join(LOCAL_DIR, skill_id)

        if not os.path.exists(skill_path):
            return {"status": "error", "message": f"Skill path does not exist: {skill_path}"}

        # 检查缓存目录中的压缩包
        cache_file_path = os.path.join(CACHE_DIR, f"{skill_id}.tar.gz")

        # 如果缓存不存在，创建压缩包
        if not os.path.exists(cache_file_path):
            with tarfile.open(cache_file_path, mode='w:gz') as tar:
                tar.add(skill_path, arcname=skill_id)

        return FileResponse(
            cache_file_path,
            media_type='application/gzip',
            filename=f'{skill_id}.tar.gz'
        )

    except Exception as e:
        return {"status": "error", "message": str(e)}


def run_fastapi():
    """在独立线程中运行 FastAPI"""
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8002, log_level="info")


if __name__ == "__main__":
    # 启动时同步一次
    try:
        sync_repo_internal()
        print(f"✅ 已加载 {len(skills)} 个技能")
        for skill_id in sorted(skills.keys()):
            print(f"   - {skill_id}")
        print()
    except Exception as e:
        print(f"⚠️  警告: {e}\n")

    print("正在启动服务器...\n")

    # 在独立线程中启动 FastAPI
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()

    print("✅ FastAPI HTTP 下载服务已启动 (port 8002)")
    print("✅ MCP 服务启动中 (port 8001)...\n")

    # 使用StreamableHttp协议运行MCP服务（阻塞主线程）
    mcp.run(transport="streamable-http", port=8001)
