# generate_2d_sketch.py
import cadquery as cq
import random

def generate_2d_sketch(retry_count=0, max_retries=5):
    """生成 2D 草图并执行布尔操作（通过 extrude 成薄片实现），然后提取所有底面的边界 Wires，并按面分组返回"""
    if retry_count >= max_retries:
        # 达到最大重试次数，返回简单的矩形草图
        print(f"警告：达到最大重试次数 {max_retries}，返回简单矩形草图")
        try:
            simple_rect = cq.Workplane("XY").rect(10, 10).extrude(-1)
            simple_wires = []
            for face in simple_rect.faces('>Z').vals():
                face_wires = [cq.Wire(wire.wrapped) for wire in face.Wires()]
                if face_wires:
                    simple_wires.append(face_wires)
            return simple_wires
        except Exception as e:
            print(f"生成简单矩形草图失败：{e}")
            return []  # 返回空列表作为最后的备选方案
    
    numPrimitives = random.randint(3, 8)
    composite_shape = None  # 3D Solid
    
    # 定义小数部分列表
    decimal_parts = [0.00, 0.25, 0.50, 0.75]

    for i in range(numPrimitives):
        primitive_type = random.choice(["Circle", "RotatedRectangle"])
        boolean_op = random.choice(["Union", "Cut", "Intersection"])

        if primitive_type == "Circle":
            # 随机选择整数部分和小数部分，然后组合成半径
            integer_part = random.randint(0, 100)  # 0到100的整数
            decimal_part = random.choice(decimal_parts)  # 从指定的小数中选择
            radius = round(integer_part + decimal_part, 2)
            # 为坐标也使用同样的方法
            center_x_integer = random.randint(-100, 100)
            center_x_decimal = random.choice(decimal_parts)
            center_y_integer = random.randint(-100, 100)
            center_y_decimal = random.choice(decimal_parts)
            center = (round(center_x_integer + center_x_decimal, 2), round(center_y_integer + center_y_decimal, 2))
            # 1. 创建 2D Face (Workplane 对象)
            primitive_2d = cq.Workplane("XY").circle(radius).translate(center)
        else:
            # 矩形的宽度和高度也使用同样方法
            width_integer = random.randint(0, 10)
            width_decimal = random.choice(decimal_parts)
            width = round(width_integer + width_decimal, 2)
            
            height_integer = random.randint(0, 10)
            height_decimal = random.choice(decimal_parts)
            height = round(height_integer + height_decimal, 2)
            
            rotation = random.randint(0, 90)  # 角度为整数
            
            # 为坐标也使用同样的方法
            center_x_integer = random.randint(-100, 100)
            center_x_decimal = random.choice(decimal_parts)
            center_y_integer = random.randint(-100, 100)
            center_y_decimal = random.choice(decimal_parts)
            center = (round(center_x_integer + center_x_decimal, 2), round(center_y_integer + center_y_decimal, 2))
            # 1. 创建 2D Face (Workplane 对象)
            primitive_2d = (
                cq.Workplane("XY")
                .rect(width, height)
                .rotate((0, 0, 0), (0, 0, 1), rotation)
                .translate(center)
            )

        # 2. 将 2D Face 拉伸成一个非常薄的 3D Solid
        # 这样就可以进行布尔运算了
        # 使用一个很小的正数高度，确保 Z=0 是底面
        try:
            #print_edge_points(primitive_2d)
            primitive = primitive_2d.extrude(-1)
        except Exception as e:
            print(f"拉伸图元失败：{e}，跳过此图元")
            continue

        if composite_shape is None:
            composite_shape = primitive
        else:
            try:
                if boolean_op == "Union":
                    # 3D Solid 与 3D Solid 进行 union
                    composite_shape = composite_shape.union(primitive)
                elif boolean_op == "Cut":  # "Cut"
                    # 3D Solid 与 3D Solid 进行 cut
                    composite_shape = composite_shape.cut(primitive)
                else:
                    composite_shape = composite_shape.intersect(primitive)
            except Exception as e:
                print(f"布尔运算 {boolean_op} 失败：{e}，跳过此操作")
                # 布尔运算失败时保持原有形状
                continue

    # 3. 提取最终形状所有底面（Z=0 平面或 Z 最小平面）的边界环 (Wires)，并按面分组
    grouped_boundary_wires = []  # 最终结果：列表的列表
    if composite_shape is not None:
        try:
            # 使用 .faces() 选择器来获取 Z 方向最小（最靠近 Z=0 或 Z 最小）的所有面
            try :
                bottom_faces_cq = composite_shape.faces('<Z')
            except Exception as e:
                face_list =composite_shape.faces().vals()
                bottom_faces_cq = composite_shape.faces('>Z')
            
            # 检查是否找到了任何面
            face_list = bottom_faces_cq.vals()
            if not face_list:
                print(f"警告：未找到底面，重试生成 (尝试 {retry_count + 1}/{max_retries})")
                return generate_2d_sketch(retry_count + 1, max_retries)

            # 遍历所有选中的底面
            for face in face_list:  # .vals() 获取 CQ 对象中的所有 Face 对象列表
                try:
                    face_wires = []  # 存储当前这个面的所有边界 Wire
                    # 遍历当前底面的边界环 (Wires)
                    wires_list = face.Wires()
                    # 添加对空列表的检查
                    if not wires_list:
                        # 如果这个面没有wire，跳过它
                        continue
                    
                    for wire in wires_list:  # 调用 Wires() 方法获取 TopoDS_Wire 集合
                        # 将 TopoDS_Wire 包装成 CadQuery 的 Wire 对象
                        try:
                            cq_wire = cq.Wire(wire.wrapped)
                            
                            # 检查wire是否退化（只有一条边且起点终点相同，或者边数为0）
                            edges = cq_wire.Edges()
                            if len(edges) == 0:
                                print(f"跳过退化的Wire：没有边")
                                continue
                            
                            # 检查是否是单边往返（起点和终点相同的单条边）
                            if len(edges) == 1:
                                edge = edges[0]
                                start_pt = edge.startPoint()
                                end_pt = edge.endPoint()
                                distance = ((end_pt.x - start_pt.x)**2 + 
                                          (end_pt.y - start_pt.y)**2 + 
                                          (end_pt.z - start_pt.z)**2)**0.5
                                if distance < 1e-6:
                                    print(f"跳过退化的Wire：单边往返（起点和终点相同）")
                                    continue
                            
                            face_wires.append(cq_wire)  # 将 Wire 添加到当前面的列表中
                        except Exception as e:
                            print(f"包装Wire对象时出错: {e}，跳过该Wire")
                            continue

                    # 将当前面的所有 Wire 组成的列表添加到最终结果列表中
                    if face_wires:  # 只添加非空的Wire列表
                        grouped_boundary_wires.append(face_wires)
                except Exception as e:
                    print(f"处理单个面时出错：{e}，跳过该面")
                    continue
        except Exception as e:
            return generate_2d_sketch(retry_count + 1, max_retries)

    # 4. 验证生成的草图
    if not grouped_boundary_wires:
        # 递归重试，带重试计数
        return generate_2d_sketch(retry_count + 1, max_retries)
    
    # 5. 返回分组的 Wire 列表：[[wire1_face1, wire2_face1, ...], [wire1_face2, wire2_face2, ...], ...]
    return grouped_boundary_wires


def print_edge_points(wire):
    """
    打印给定Wire上所有边缘的点的位置坐标
    """
    print(f"Wire包含 {len(wire.Edges())} 条边")
    for i, edge in enumerate(wire.Edges()):
        print(f"  边 {i+1}:")
        # 获取边的顶点
        vertices = edge.Vertices()
        for j, vertex in enumerate(vertices):
            point = vertex.toTuple()
            print(f"    顶点 {j+1}: ({point[0]:.3f}, {point[1]:.3f}, {point[2]:.3f})")


# --- 示例 ---
if __name__ == "__main__":
    print("Testing generate_2d_sketch (returns grouped Wires from 3D boolean operations)...")
    try:
        grouped_wires = generate_2d_sketch()
        print(
            f"Generated {len(grouped_wires)} groups of wires (representing {len(grouped_wires)} distinct 2D regions).")
        for i, wire_group in enumerate(grouped_wires):
            print(f"  Group {i + 1} (from one 2D region):")
            for j, w in enumerate(wire_group):
                print(f"    Wire {j + 1} has {len(w.Edges())} edges.")
                # 打印边缘点位置
                print_edge_points(w)
                # 可选：检查 Wire 是否在 Z=0 平面上 (或 Z=min 平面)
                if w.Vertices():
                    # 修正：使用 .Point() 获取 Vertex 的坐标向量
                    vertex_cq_obj = w.Vertices()[0]  # 获取 CQ Vertex 对象
                    vertex_point = vertex_cq_obj.toTuple()  # 返回 (x, y, z) 元组
                    print(
                        f"      Example vertex (x,y,z): ({vertex_point[0]:.3f}, {vertex_point[1]:.3f}, {vertex_point[2]:.3f})")
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback

        traceback.print_exc()  # 打印更详细的错误信息
