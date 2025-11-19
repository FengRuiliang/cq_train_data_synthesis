def validate_cad_model(cad_model):
    """
    验证 CAD 模型有效性（检查是否为单一、连通的有效实体）。

    Args:
        cad_model: CadQuery Workplane 或 Shape 对象。

    Returns:
        cad_model: 如果模型有效且为单一连通实体，则返回原始模型。
        None: 如果模型无效、不是单一实体或发生错误。
    """
    try:
        # 1. 检查是否为有效的 CadQuery 对象
        # (这一步 .val() 本身就会检查对象是否正确封装了底层几何体)
        # solid = cad_model.val() # 可选：如果只需要底层对象验证，可以保留

        # 2. 检查是否包含 Solid 几何体
        # 使用 .solids() 选择器获取所有 Solid 对象
        solid_objects = cad_model.solids() # 返回一个 Workplane 对象，其栈中包含 Solid

        # 3. 检查 Solid 的数量 (确保只有一个连通区域/实体)
        num_solids = solid_objects.size() # 获取 Solid 对象的数量
        if num_solids != 1:
            print(f"  Validation failed: Model contains {num_solids} solid(s), expected exactly 1 for a single connected region.")
            return None

        # 4. 检查唯一 Solid 的有效性
        # 获取第一个（也是唯一的）Solid 对象
        # solid = solid_objects.val() # 获取第一个 Solid (CQ object)
        # 或者获取底层的 OCP 对象进行验证
        ocp_solid = solid_objects.objects[0].wrapped # 获取底层 TopoDS_Solid
        from OCP.BRepCheck import BRepCheck_Analyzer
        from OCP import BRep # Ensure BRep is imported for BRepCheck_Analyzer constructor
        # Note: BRepCheck_Analyzer constructor might need BRep as first argument in some OCP versions
        # analyzer = BRepCheck_Analyzer(ocp_solid)
        # is_valid_shape = analyzer.IsValid()
        # For simplicity and consistency with the original, we use the CQ object's isValid()
        cq_solid = solid_objects.val() # 获取 CQ Solid 对象
        is_valid_shape = cq_solid.isValid()

        if not is_valid_shape:
            print("  Validation failed: The single solid in the model is not geometrically/topologically valid.")
            return None

        # 如果所有检查都通过
        print("  Validation passed: Model is a single, connected, valid solid.")
        return cad_model

    except Exception as e:
        print(f"  Validation failed with an exception: {e}")
        return None

# --- 示例 ---
if __name__ == "__main__":
    import cadquery as cq

    print("--- 测试单一有效实体 ---")
    single_box = cq.Workplane("XY").box(1, 1, 1)
    result1 = validate_cad_model(single_box)
    print(f"单一立方体验证结果: {result1 is not None}\n")

    print("--- 测试多个实体 (Union) ---")
    box1 = cq.Workplane("XY").box(1, 1, 1)
    box2 = cq.Workplane("XY").box(1, 1, 1).translate((2, 0, 0)) # 分开一定距离
    multi_union = box1.union(box2)
    result2 = validate_cad_model(multi_union)
    print(f"两个立方体 Union 验证结果: {result2 is not None}\n")

    print("--- 测试多个实体 (Cut - 通常仍为单实体) ---")
    base_box = cq.Workplane("XY").box(2, 2, 2)
    cut_cyl = cq.Workplane("XY").circle(0.5).extrude(3) # 比盒子高，确保完全穿透
    single_with_hole = base_box.cut(cut_cyl)
    result3 = validate_cad_model(single_with_hole)
    print(f"带孔立方体 (单实体) 验证结果: {result3 is not None}\n")

    print("--- 测试无效实体 (自相交) ---")
    # 创建一个可能导致自相交的形状，例如一个非常小的圆柱体与一个大圆柱体相减
    # 这个例子可能在某些 CadQuery/OCC 版本下不会产生无效几何，但可以尝试
    large_cyl = cq.Workplane("XY").circle(1).extrude(1)
    # 尝试一个更可能产生无效结果的操作，例如非常薄的拉伸然后切割
    # 或者尝试将一个物体完全挖空，但这通常会返回空或不同的有效形状
    # 一个更可靠的无效形状生成方式可能比较复杂，这里演示结构
    # 创建一个内部有冲突的草图然后拉伸通常更容易产生无效实体
    # 比如，在一个面上创建一个比面还大的切割草图
    base_face = cq.Workplane("XY").rect(1, 1).faces().val()
    # 在一个内部创建一个更大的矩形草图进行切割，这可能导致无效面，进而拉伸成无效体
    # 这在 Workplane 级别通常会被处理或报错，直接用 OCP 操作才更容易产生无效实体
    # 对于 CadQuery 用户，一个无效实体的例子可能来自非常复杂的布尔运算失败
    # 这里我们暂时跳过直接生成无效实体的复杂例子，重点演示逻辑
    # 假设我们有一个已知无效的 cad_model 对象 invalid_model
    # result4 = validate_cad_model(invalid_model)
    # print(f"无效实体验证结果: {result4 is not None}\n")
    # 由于难以用基本 Workplane 操作构造一个无效 Solid，我们跳过这个具体例子
    # 但函数逻辑已覆盖了 .isValid() 返回 False 的情况
    print("--- 跳过无效实体测试 (构造复杂) ---")
    print(" (函数逻辑已覆盖 .isValid() 为 False 的情况)\n")

    print("--- 测试非 Solid 对象 (例如 Wire) ---")
    wire_obj = cq.Workplane("XY").circle(1).wire()
    result5 = validate_cad_model(wire_obj)
    print(f"Wire 对象验证结果: {result5 is not None}\n") # 应该返回 None，因为没有 Solid