def generate_face_select_code(face_identifier):
    """生成自定义面的select代码，仅处理'Face:...'格式"""
    if isinstance(face_identifier, str) and face_identifier.startswith('Face:'):
        return (
            f"face = result.faces('{face_identifier}').val()\n"
            f"plane = cq.Plane(origin=face.Center(), normal=face.normalAt())"
        )
    return ""


def generate_workplane_str(plane):
    """
    生成工作平面字符串，确保平面名称始终被单引号包裹
    - 带origin的平面：为平面名称添加单引号（如'XZ', origin=(...) → 'XZ', origin=(...)）
    - 基础平面（XY/YZ/XZ）：直接返回带单引号的格式（如'YZ'）
    - 自定义面：返回"face"
    """
    if isinstance(plane, str):
        if 'origin=' in plane:
           return plane
        elif plane.startswith('Face:'):
            return "plane"
        else:
            # 基础平面直接添加单引号
            return f"'{plane}'"
    return "plane"

def generate_extruded_cq_code(
    extrude_id,
    plane,
    wires_for_one_region,
    extrude_height=1.0,
):
    """生成拉伸代码，统一格式：extrude_{id} = ... + 布尔运算"""
    from .sketch_code_generator import generate_sketch_code

    # 处理空Wire列表 - 修复版本
    if not wires_for_one_region:
        var_name = f"extrude_{extrude_id}"
        # 使用空形状而非极小实体，避免后续操作错误
        return f"{var_name} = cq.Workplane('XY')  # 空Wire列表，生成空形状"

    # 生成并过滤草图代码
    base_sketch_code = generate_sketch_code(wires_for_one_region)
    lines = base_sketch_code.split('\n')
    if not lines:
        var_name = f"extrude_{extrude_id}"
        return f"{var_name} = cq.Workplane('XY')  # 无效草图代码，生成空形状"

    filtered_lines = [line for line in lines
                      if not line.strip().startswith("result = (")]

    # 生成工作平面相关代码
    face_select_code = generate_face_select_code(plane)
    workplane_ref = generate_workplane_str(plane)
    workplane_str = f"cq.Workplane({workplane_ref})"

    # 替换默认Workplane
    if filtered_lines and "cq.Workplane('XY')" in filtered_lines[0]:
        filtered_lines[0] = filtered_lines[0].replace("cq.Workplane('XY')", workplane_str)

    # 添加拉伸操作
    last_non_empty_idx = len(filtered_lines) - 1
    while last_non_empty_idx >= 0 and not filtered_lines[last_non_empty_idx].strip():
        last_non_empty_idx -= 1
    if last_non_empty_idx >= 0:
        filtered_lines.insert(last_non_empty_idx, f"    .extrude({extrude_height})")
    else:
        filtered_lines.append(f"    .extrude({extrude_height})")

    # 移除多余括号并组合代码
    final_sketch_lines = [line for line in filtered_lines if line.strip() != ")"]
    sketch_code = "\n".join(final_sketch_lines)
    var_name = f"extrude_{extrude_id}"
    prefix_code = f"{face_select_code}\n" if face_select_code else ""

    full_code = (
        f"{prefix_code}"
        f"{var_name} = (\n{sketch_code}\n)\n"
    )

    return full_code


# --- 示例用法（修复初始化逻辑） ---
if __name__ == "__main__":
    import cadquery as cq
    from generate_cq_code.generate_sketch_code import generate_2d_sketch

    # 修复：用极小非零实体初始化result（1e-6=0.000001，避免退化实体错误）
    init_code = """import cadquery as cq
from cadquery_tracker import create_tracker

# 创建追踪器实例
tracker = create_tracker()
"""
    print("=== 初始化代码 ===")
    print(init_code)
    try:
        exec(init_code)
        print("✅ 初始化成功：生成极小基础实体\n")
    except Exception as e:
        print(f"❌ 初始化失败：{e}\n")
        exit()

    # 获取测试Wire组
    all_wires_grouped = generate_2d_sketch()
    if not all_wires_grouped:
        print("未生成有效Wire组，测试终止")
        exit()

    selected_wires = all_wires_grouped[0]
    print(f"使用第1个Wire组（共{len(selected_wires)}个Wire）测试\n")

    # 测试1：基础平面XY（ID=1，union运算）
    print("=== 测试1：基础平面XY ===")
    code1 = generate_extruded_cq_code(
        extrude_id=1,
        plane='XY',
        wires_for_one_region=selected_wires,
        extrude_height=0.5,
    )
    print(code1)
    try:
        exec(code1)
        print("✅ 执行成功：生成extrude_1并合并到result\n")
    except Exception as e:
        print(f"❌ 执行失败：{e}\n")

    # 测试2：自定义面标识（ID=2，cut运算）
    print("=== 测试2：自定义面标识 ===")
    custom_face = "Face:(extrude.1;0:Wire:(Sketch.1;5))"
    code2 = generate_extruded_cq_code(
        extrude_id=2,
        plane=custom_face,
        wires_for_one_region=selected_wires,
        extrude_height=0.3,
    )
    print(code2)
    try:
        exec(code2)
        print("✅ 执行成功：生成extrude_2并切割result\n")
    except Exception as e:
        print(f"❌ 执行失败：{e}\n")

    # 测试3：cq.Plane对象（ID=3，intersect运算）
    print("=== 测试3：cq.Plane对象 ===")
    custom_plane = cq.Plane(origin=(0, 0, 0.5), normal=(0, 0, 1))
    code3 = generate_extruded_cq_code(
        extrude_id=3,
        plane=custom_plane,
        wires_for_one_region=selected_wires,
        extrude_height=0.4,
    )
    print(code3)
    try:
        plane = custom_plane  # 为exec提供plane变量
        exec(code3)
        print("✅ 执行成功：生成extrude_3并与result求交")
    except Exception as e:
        print(f"❌ 执行失败：{e}")
