import random
import sys
import cadquery as cq  # 补充导入，用于生成包围盒平面
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GeomAbs import GeomAbs_Line


from .sketch_generator import generate_2d_sketch
from .extrude_code_generator import generate_extruded_cq_code
from .code_validator import validate_code_volume_change


class CADCodeGenerator:
    def __init__(self, min_opera_cnt=0, max_opera_cnt=30):
        self.plane_candidates = ['XY', 'YZ', 'XZ']  # 原始候选平面（固定不变）
        self.latest_bbox_planes = []  # 新增：存储最新的包围盒平面
        self.sketch_pool = []
        self.used_sketches = []
        self.next_sketch_id = 1
        self.generated_extrudes = []
        self.next_extrude_id = 1
        self.min_opera_cnt = min_opera_cnt
        self.max_opera_cnt = max_opera_cnt

    def get_random_cad_plane(self):
        """组合原始候选平面和最新包围盒平面，随机选择一个"""
        # 合并原始平面和最新包围盒平面（去重）
        combined_planes = list(set(self.plane_candidates + self.latest_bbox_planes))
        if not combined_planes:
            raise ValueError("候选平面集合为空")
        return random.choice(combined_planes)

    def get_sketch_from_pool(self, reuse_prob=0.3):
        """
        从草图池或已使用草图中选择（带复用概率）
        :param reuse_prob: 从已使用草图中选择的概率（0~1之间）
        """
        # 先判断是否有已使用的草图，且触发复用概率
        if self.used_sketches and random.random() < reuse_prob:
            # 从已使用草图中随机选择一个
            selected_item = random.choice(self.used_sketches)
            selected_sketch = selected_item['sketch']
            # 为复用的草图分配新ID（保持ID唯一性）
            current_sketch_id = self.next_sketch_id
            # 注意：这里不再增加next_sketch_id，由调用者在确认使用后增加
            return selected_sketch, current_sketch_id

        # 从草图池中获取或生成新草图
        if not self.sketch_pool:
            self.sketch_pool = generate_2d_sketch()

        if self.sketch_pool:
            # 从池中随机选择一个草图
            selected_sketch = self.sketch_pool.pop()
            current_sketch_id = self.next_sketch_id
            # 注意：这里不再增加next_sketch_id，由调用者在确认使用后增加
        else:
            # 极端情况：池为空也无复用，则创建简单矩形草图
            simple_sketch = [[
                (-5, -5), (5, -5), (5, 5), (-5, 5)
            ]]
            selected_sketch = simple_sketch
            current_sketch_id = self.next_sketch_id
            # 注意：这里不再增加next_sketch_id，由调用者在确认使用后增加

        # 记录已使用的草图（用于后续复用）
        self.used_sketches.append({
            'id': current_sketch_id,
            'sketch': selected_sketch
        })

        return selected_sketch, current_sketch_id

    def get_sketch_by_id(self, sketch_id):
        for item in self.used_sketches:
            if item['id'] == sketch_id:
                return item['sketch']
        return None

    def calculate_sketch_edges(self, sketch):
        total_edges = 0
        for wire in sketch:
            total_edges += len(wire.Edges())
        return total_edges

    def generate_face_identifiers(self, extrude_id, sketch_id, sketch):
        total_edges = self.calculate_sketch_edges(sketch)
        face_identifiers = [
            f"Face:(Extrude.{extrude_id};1)",
            f"Face:(Extrude.{extrude_id};2)"
        ]
        cumulative_edge_num = 0
        for wire in sketch:
            edges = wire.Edges()
            for edge in edges:
                cumulative_edge_num += 1
                adaptor = BRepAdaptor_Curve(edge.wrapped)
                if adaptor.GetType() == GeomAbs_Line:
                    # 修复：确保面选择器格式正确，添加缺失的内部括号
                    side_face_id = f"Face:(Extrude.{extrude_id};0:(Wire:(Sketch.{sketch_id};{cumulative_edge_num})))"
                    face_identifiers.append(side_face_id)
        return face_identifiers

    @staticmethod
    def generate_bbox_plane_strings(workplane):
        """生成包围盒平面字符串（静态方法，通过工作平面计算）"""
        try:
            shape = workplane.val()
            # 检查shape是否有效
            if shape.isValid() is False:
                return []  # 返回空列表而不是抛出异常
                
            bbox = shape.BoundingBox()
            x_min, x_max = bbox.xmin, bbox.xmax
            y_min, y_max = bbox.ymin, bbox.ymax
            z_min, z_max = bbox.zmin, bbox.zmax
            return [
                f"'XY', origin=(0.0, 0.0, {z_max:.2f})",
                f"'XY', origin=(0.0, 0.0, {z_min:.2f})",
                f"'YZ', origin=({x_max:.2f}, 0.0, 0.0)",
                f"'YZ', origin=({x_min:.2f}, 0.0, 0.0)",
                f"'XZ', origin=(0.0, {y_max:.2f}, 0.0)",
                f"'XZ', origin=(0.0, {y_min:.2f}, 0.0)",
            ]
        except Exception as e:
            # 发生任何异常时返回空列表
            return []

    def generate_and_record_extrude(self, sketch, sketch_id, plane):
        current_extrude_id = self.next_extrude_id
        # 注意：这里不再增加next_extrude_id，由调用者在确认使用后增加
        extrude_height = round(random.uniform(-100, 100), 2)
        code = generate_extruded_cq_code(
            extrude_id=current_extrude_id,
            plane=plane,
            wires_for_one_region=sketch,
            extrude_height=extrude_height,
        )
        self.generated_extrudes.append({
            'id': current_extrude_id,
            'code': code,
            'sketch_id': sketch_id,
            'plane': plane,
            'height': extrude_height
        })
        # 生成面标识符但不立即添加到候选列表，返回给调用者决定是否添加
        new_face_identifiers = self.generate_face_identifiers(current_extrude_id, sketch_id, sketch)

        return f"extrude_{sketch_id}", code, new_face_identifiers

    def generate_cq_code(self):
        """逐步生成代码，跳过结果未变化的循环（修复Volume属性错误）"""
        full_code = (
            "import cadquery as cq\n"
            "from cadquery_tracker import create_tracker\n\n"
            "# 创建追踪器实例\n"
            "tracker = create_tracker()\n\n"
        )

        loop_count = random.randint(self.min_opera_cnt, self.max_opera_cnt)
        if loop_count == 0:
            print("生成0次拉伸，返回基础代码")
            return full_code

        # 记录上一次的实体属性（用于重复判断）
        last_volume = None  # 上一次有效实体的体积
        valid_code_fragments = []  # 仅保存有效的代码片段

        for i in range(loop_count):
            # 1. 选择平面
            plane = self.get_random_cad_plane()
            # 2. 获取草图并生成拉伸代码
            sketch, sketch_id = self.get_sketch_from_pool()
            extrude_var, current_code, new_face_identifiers = self.generate_and_record_extrude(
                sketch=sketch,
                sketch_id=sketch_id,
                plane=plane
            )
            # 3. 生成布尔运算代码
            if not valid_code_fragments:  # 首次有效操作
                boolean_code = f"result = {extrude_var}"
            else:
                boolean_op = random.choice(['cut', 'union'])
                boolean_code = f"result = result.{boolean_op}({extrude_var})"

            # 4. 临时拼接当前循环代码，用于执行判断
            current_loop_code = f"{current_code}{boolean_code}\n"
            temp_full_code = full_code + "".join(valid_code_fragments) + current_loop_code

            # 5. 使用子进程验证代码，判断结果是否变化
            is_valid, is_changed, current_volume, error_msg = validate_code_volume_change(
                temp_full_code, 
                last_volume
            )
            
            if is_valid:
                # 检查体积是否为0或接近0（说明实体被完全消除）
                if current_volume is not None and abs(current_volume) < 1e-6:
                    print(f"第{i + 1}次循环：体积为0，实体被完全消除，跳过此次代码")
                    # 移除生成的extrude记录
                    if self.generated_extrudes:
                        self.generated_extrudes.pop()
                elif is_changed:
                    valid_code_fragments.append(current_loop_code)
                    last_volume = current_volume
                    print(f"第{i + 1}次循环：结果有变化，保留代码（体积={current_volume:.6f}）")
                    # 只有成功拼接才更新 next_id
                    self.next_sketch_id += 1
                    self.next_extrude_id += 1
                    
                    # 只有在操作成功时才添加面标识符到候选列表
                    for face_id in new_face_identifiers:
                        if face_id not in self.plane_candidates:
                            self.plane_candidates.append(face_id)
                    
                    # 更新包围盒平面（需要在主进程中执行以获取workplane）
                    try:
                        # 在主进程中执行代码以获取result用于计算包围盒
                        exec_globals = {'cq': cq, 'cadquery': cq}
                        local_vars = {}
                        exec(temp_full_code, exec_globals, local_vars)
                        current_result = local_vars.get('result')
                        if current_result:
                            bbox_planes = self.generate_bbox_plane_strings(current_result)
                            if bbox_planes:
                                self.latest_bbox_planes = bbox_planes
                    except:
                        # 如果包围盒计算失败，不影响主流程
                        pass
                else:
                    print(f"第{i + 1}次循环：结果未变化，跳过此次代码（体积={current_volume:.6f}）")
                    # 移除生成的extrude记录（面标识符未添加，无需清除）
                    if self.generated_extrudes:
                        self.generated_extrudes.pop()
            else:
                # 验证失败
                print(f"第{i + 1}次循环执行失败：{error_msg}，跳过此次代码")
                # 移除可能已添加的extrude记录（面标识符未添加，无需清除）
                if self.generated_extrudes:
                    self.generated_extrudes.pop()

        # 拼接最终有效代码
        full_code += "\n".join(valid_code_fragments)
        print(f"完成{loop_count}次循环，有效代码共{len(valid_code_fragments)}段")
        return full_code

# 测试部分
if __name__ == "__main__":
    print("开始测试代码生成功能...\n")

    # 每次生成创建新实例，自动复位状态å
    generator = CADCodeGenerator()
    try:
        full_code = generator.generate_cq_code()
        print(f"\n=== 生成的完整代码（前800字符） ===")
        print(full_code[:800] + ("..." if len(full_code) > 800 else ""))

        print(f"\n=== 生成记录验证 ===")
        print(f"实际生成extrude数量：{len(generator.generated_extrudes)}")
        if generator.generated_extrudes:
            print(f"extrude ID序列：{[e['id'] for e in generator.generated_extrudes]}")
    except Exception as e:
        print(f"测试失败：{e}")
