import cadquery as cq
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GeomAbs import GeomAbs_Line, GeomAbs_Circle, GeomAbs_Ellipse
import math

def generate_sketch_code(wires):
    """
    根据输入的Wire列表生成Workplane代码
    :param wires: 包含多个Wire对象的列表（每个Wire是一个闭合环）
    :return: 生成的CadQuery Workplane代码字符串
    """
    if not wires:
        return "result = cq.Workplane('XY')"

    lines = ["result = (", "    cq.Workplane('XY')"]

    for wire_idx, wire in enumerate(wires):
        edges = wire.Edges()
        if not edges:
            continue

        # 检查是否是单个边的完整圆
        if len(edges) == 1:
            edge = edges[0]
            adaptor = BRepAdaptor_Curve(edge.wrapped)
            curve_type = adaptor.GetType()
            if curve_type == GeomAbs_Circle:
                # 检查是否是完整圆：参数范围是否为 2π
                u1 = adaptor.FirstParameter()
                u2 = adaptor.LastParameter()
                if abs((u2 - u1) - 2 * math.pi) < 1e-5: # 允许微小误差
                    # 是完整圆
                    geom_circle = adaptor.Circle()
                    radius = geom_circle.Radius()
                    center = geom_circle.Location()
                    # Workplane.circle 从当前点为圆心画圆，或用 moveTo 移动到圆心
                    # 为了与路径一致，我们先 moveTo 圆心
                    lines.append(f"    .moveTo({round(center.X(), 2):.2f}, {round(center.Y(), 2):.2f})")
                    lines.append(f"    .circle({round(radius, 2):.2f})")
                    continue # 处理完完整圆就跳过下面的常规处理

        # 非完整圆的通用处理 - 需要重新排序边以形成连续路径
        # 首先收集所有边的信息
        edge_info_list = []
        for edge in edges:
            start_pt = edge.startPoint()
            end_pt = edge.endPoint()
            adaptor = BRepAdaptor_Curve(edge.wrapped)
            curve_type = adaptor.GetType()
            edge_info_list.append({
                'edge': edge,
                'start': start_pt,
                'end': end_pt,
                'adaptor': adaptor,
                'curve_type': curve_type,
                'used': False
            })
        
        # 从第一条边开始，构建连续路径
        if not edge_info_list:
            continue
            
        # 选择第一条边
        current_edge_info = edge_info_list[0]
        current_edge_info['used'] = True
        first_pt = current_edge_info['start']
        last_pt = current_edge_info['end']
        
        lines.append(f"    .moveTo({round(first_pt.x, 2):.2f}, {round(first_pt.y, 2):.2f})")
        
        # 生成第一条边的代码
        if current_edge_info['curve_type'] == GeomAbs_Line:
            lines.append(f"    .lineTo({round(last_pt.x, 2):.2f}, {round(last_pt.y, 2):.2f})")
        elif current_edge_info['curve_type'] == GeomAbs_Circle:
            mid_pt = current_edge_info['edge'].positionAt(0.5)
            v1_x = mid_pt.x - first_pt.x
            v1_y = mid_pt.y - first_pt.y
            v2_x = last_pt.x - first_pt.x
            v2_y = last_pt.y - first_pt.y
            cross_product = abs(v1_x * v2_y - v1_y * v2_x)
            if cross_product < 1e-10:
                lines.append(f"    .lineTo({round(last_pt.x, 2):.2f}, {round(last_pt.y, 2):.2f})")
            else:
                lines.append(
                    f"    .threePointArc(({round(mid_pt.x, 2):.2f}, {round(mid_pt.y, 2):.2f}), "
                    f"({round(last_pt.x, 2):.2f}, {round(last_pt.y, 2):.2f}))"
                )
        
        # 处理剩余的边
        for _ in range(len(edge_info_list) - 1):
            # 找到下一条连接的边
            next_edge_info = None
            min_dist = float('inf')
            reverse_next = False
            
            for edge_info in edge_info_list:
                if edge_info['used']:
                    continue
                
                # 检查这条边的起点或终点是否接近last_pt
                dist_to_start = math.sqrt((edge_info['start'].x - last_pt.x)**2 + 
                                         (edge_info['start'].y - last_pt.y)**2)
                dist_to_end = math.sqrt((edge_info['end'].x - last_pt.x)**2 + 
                                       (edge_info['end'].y - last_pt.y)**2)
                
                if dist_to_start < min_dist:
                    min_dist = dist_to_start
                    next_edge_info = edge_info
                    reverse_next = False
                
                if dist_to_end < min_dist:
                    min_dist = dist_to_end
                    next_edge_info = edge_info
                    reverse_next = True
            
            if next_edge_info is None or min_dist > 1e-3:
                # 找不到连接的边，可能是断开的路径
                break
            
            next_edge_info['used'] = True
            
            # 确定边的方向
            if reverse_next:
                start_pt = next_edge_info['end']
                end_pt = next_edge_info['start']
            else:
                start_pt = next_edge_info['start']
                end_pt = next_edge_info['end']
            
            # 检查是否是重复点或回到起点的边
            edge_length = math.sqrt((end_pt.x - last_pt.x)**2 + (end_pt.y - last_pt.y)**2)
            distance_to_start = math.sqrt((end_pt.x - first_pt.x)**2 + (end_pt.y - first_pt.y)**2)
            
            # 如果这条边长度为0，跳过
            if edge_length < 1e-6:
                continue
            
            # 如果这条边的终点回到起点，跳过（因为close()会自动闭合）
            if distance_to_start < 1e-6:
                # 这条边回到起点，跳过它，让close()来闭合路径
                continue
            
            last_pt = end_pt
            
            # 生成代码
            if next_edge_info['curve_type'] == GeomAbs_Line:
                lines.append(f"    .lineTo({round(end_pt.x, 2):.2f}, {round(end_pt.y, 2):.2f})")

            elif next_edge_info['curve_type'] == GeomAbs_Circle:
                # 对于圆弧，需要根据方向获取正确的中点
                edge = next_edge_info['edge']
                if reverse_next:
                    # 边是反向的，需要反向获取中点
                    mid_pt = edge.positionAt(0.5)
                    # 重新计算三点，确保顺序正确
                    actual_start = start_pt
                    actual_end = end_pt
                else:
                    mid_pt = edge.positionAt(0.5)
                    actual_start = start_pt
                    actual_end = end_pt
                
                # 检查三点是否共线
                v1_x = mid_pt.x - actual_start.x
                v1_y = mid_pt.y - actual_start.y
                v2_x = actual_end.x - actual_start.x
                v2_y = actual_end.y - actual_start.y
                cross_product = abs(v1_x * v2_y - v1_y * v2_x)
                
                if cross_product < 1e-10:
                    lines.append(f"    .lineTo({round(actual_end.x, 2):.2f}, {round(actual_end.y, 2):.2f})")
                else:
                    lines.append(
                        f"    .threePointArc(({round(mid_pt.x, 2):.2f}, {round(mid_pt.y, 2):.2f}), "
                        f"({round(actual_end.x, 2):.2f}, {round(actual_end.y, 2):.2f}))"
                    )

        # 始终添加 close()，CadQuery 需要它来创建 wire
        lines.append("    .close()")

    lines.append(")")
    return "\n".join(lines)


# 示例验证
if __name__ == "__main__":
    # 创建示例Wire（矩形环 + 圆环）
    rect_wire = cq.Workplane("XY").rect(2, 1).wires().val()  # 矩形Wire
    circle_wire = cq.Workplane("XY").circle(1).wires().val()  # 圆形Wire
    # 添加一个半圆测试
    half_circle_wire = cq.Workplane("XY").moveTo(-1, 0).threePointArc((0, 1), (1, 0)).close().wires().val()

    sample_wires = [rect_wire, circle_wire, half_circle_wire] # 包含完整圆、半圆、矩形

    # 生成代码
    workplane_code = generate_sketch_code(sample_wires)
    print("Generated Workplane Code:")
    print(workplane_code)

    # 可选：尝试执行生成的代码（调试用）
    print("\n--- Executing Generated Code ---")
    try:
        exec(workplane_code)
        print("✅ 生成的代码执行成功！")
        print(f"Result type: {type(result)}")
        # 尝试拉伸看看是否有效
        extruded = result.extrude(0.1)
        print(f"Extruded type: {type(extruded)}")
    except Exception as e:
        print(f"❌ 执行失败: {e}")
