from fastapi import APIRouter

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/import")
def agent_import_placeholder():
    return {
        "message": "预留接口：未来用于智能体批量导入企业数据"
    }


@router.get("/search")
def agent_search_placeholder():
    return {
        "message": "预留接口：未来用于智能体搜索候选企业"
    }


@router.get("/stats")
def agent_stats_placeholder():
    return {
        "message": "预留接口：未来用于智能体统计分析"
    }