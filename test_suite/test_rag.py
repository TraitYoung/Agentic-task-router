from hybrid_engine import HybridRetriever
from tools.ai_client import get_embedding


def final_sanity_check() -> None:
    retriever = HybridRetriever()
    query = "关于 Career_Nuke 的长线职业规划是什么？"
    print(f"🔍 正在执行混合检索: {query}")

    # 计算查询向量（真实 text-embedding-3-small 向量）
    query_embedding = get_embedding(query)

    # 混合检索：限定在主线程 + Q2 战略库中寻找长期规划相关记忆
    results = retriever.search_hybrid(
        query=query,
        query_embedding=query_embedding,
        top_k=3,
        thread_id="TraitYoung_Main",
        quadrant="Q2",
    )

    print("\n[ Axiodrasil 记忆提取结果 ]")
    if not results:
        print("（未检索到任何相关记忆，请确认 Q2 迁移是否已完成，以及数据库中是否存在相关内容。）")
        return

    # 主命中：RRF 排名第一的记忆
    best = results[0]
    best_full = (best["content"] or "").replace("\n", " ")
    print("【主命中】")
    print(f"[{best['quadrant']}] {best_full}\n")

    # 其他候选：仅用于审计与调试
    if len(results) > 1:
        print("【其他候选】")
        for res in results[1:]:
            snippet = (res["content"] or "")[:100].replace("\n", " ")
            print(f"- [{res['quadrant']}] {snippet}...")


if __name__ == "__main__":
    final_sanity_check()
