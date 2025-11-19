import os
import shutil
from tqdm import tqdm  # 用于显示进度条（需安装：pip install tqdm）
from generators.code_generator import CADCodeGenerator

def save_cq_code_to_file(code, base_dir="data/SyntheticData", batch_size=10000):
    """
    将生成的CadQuery代码保存为.py文件，按批次存放

    Args:
        code (str): 生成的CAD模型代码
        base_dir (str): 根目录路径
        batch_size (int): 每批文件数量（默认10000）
    Returns:
        str: 保存的文件路径
    """
    # 确保根目录存在
    os.makedirs(base_dir, exist_ok=True)

    # 计算当前总文件数（用于确定批次和文件名）
    total_files = 0
    batch_dirs = [d for d in os.listdir(base_dir) if
                  os.path.isdir(os.path.join(base_dir, d)) and d.startswith("batch_")]
    if batch_dirs:
        # 从最大批次目录中统计已有文件数
        last_batch = max(batch_dirs, key=lambda x: int(x.split("_")[1]))
        last_batch_path = os.path.join(base_dir, last_batch)
        total_files = (int(last_batch.split("_")[1]) * batch_size) + len(os.listdir(last_batch_path))
    current_batch = total_files // batch_size
    current_idx = total_files % batch_size

    # 构建批次目录和文件路径
    batch_dir = os.path.join(base_dir, f"batch_{current_batch}")
    os.makedirs(batch_dir, exist_ok=True)
    file_path = os.path.join(batch_dir, f"cad_model_{total_files}.py")

    # 写入代码（添加文件头说明）
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("# 自动生成的CAD模型训练数据\n")
        f.write("# 包含随机生成的草图、拉伸及布尔运算\n")
        f.write(code)

    return file_path


def save_cq_code_sequence(cq_code, base_dir="data/SyntheticData", batch_size=10000):
    """
    将生成的CadQuery代码拆分成多个文件，每个文件在前一个文件基础上增加一个操作
    
    Args:
        cq_code (str): 完整的生成CAD模型代码
        base_dir (str): 根目录路径
        batch_size (int): 每批文件数量
    
    Returns:
        int: 生成的文件数量
    """
    # 确保根目录存在
    os.makedirs(base_dir, exist_ok=True)

    # 计算当前总文件数（用于确定批次和文件名）
    total_files = 0
    batch_dirs = [d for d in os.listdir(base_dir) if
                  os.path.isdir(os.path.join(base_dir, d)) and d.startswith("batch_")]
    if batch_dirs:
        # 从最大批次目录中统计已有文件数
        last_batch = max(batch_dirs, key=lambda x: int(x.split("_")[1]))
        last_batch_path = os.path.join(base_dir, last_batch)
        total_files = (int(last_batch.split("_")[1]) * batch_size) + len(os.listdir(last_batch_path))
    
    # 按行分割代码
    lines = cq_code.split('\n')
    
    # 分离导入语句和操作代码
    header_lines = []
    operation_lines = []
    
    for line in lines:
        if line.startswith("import "):
            header_lines.append(line)
        else:
            operation_lines.append(line)
    
    # 找到所有result=行的索引
    result_indices = []
    for i, line in enumerate(operation_lines):
        if line.strip().startswith("result = "):
            result_indices.append(i)
    
    # 如果没有找到result行，将整个代码作为一个文件保存
    if not result_indices:
        result_indices = [len(operation_lines) - 1]
    
    # 为每个result=行创建一个文件
    for i, result_idx in enumerate(result_indices):
        # 构建当前步骤的代码
        current_code_lines = header_lines.copy()
        # 添加到当前result行为止的所有行
        current_code_lines.extend(operation_lines[:result_idx + 1])
        
        current_code = "\n".join(current_code_lines)
        
        # 计算批次和文件路径
        current_total_files = total_files + i
        current_batch = current_total_files // batch_size
        current_idx = current_total_files % batch_size

        # 构建批次目录和文件路径
        batch_dir = os.path.join(base_dir, f"batch_{current_batch}")
        os.makedirs(batch_dir, exist_ok=True)
        file_path = os.path.join(batch_dir, f"cad_model_{current_total_files}.py")

        # 写入代码
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("# 自动生成的CAD模型训练数据\n")
            f.write(f"# 包含随机生成的草图、拉伸及布尔运算（第{i+1}步，共{len(result_indices)}步）\n")
            f.write(current_code)
    
    return len(result_indices)


def generate_training_dataset(total_count=1000000, batch_size=10000, clear_existing=False):
    """
    生成指定数量的CAD模型训练文件

    Args:
        total_count (int): 总文件数（默认100万）
        batch_size (int): 每批文件数量（默认10000）
        clear_existing (bool): 是否清空现有目录（默认False，需要显式指定）
    """
    base_dir = "../data/SyntheticData"

    # 安全的目录清空逻辑
    if os.path.exists(base_dir):
        if clear_existing:
            # 添加安全检查：确保路径包含 SyntheticData
            if "SyntheticData" not in base_dir:
                raise ValueError(f"安全检查失败：路径 {base_dir} 不包含 'SyntheticData'，拒绝删除")
            
            # 检查目录中是否有文件
            file_count = sum(len(files) for _, _, files in os.walk(base_dir))
            if file_count > 0:
                print(f"警告：目录 {base_dir} 包含 {file_count} 个文件")
                response = input(f"确认删除目录 {base_dir} 及其所有内容？(yes/no): ")
                if response.lower() != 'yes':
                    print("操作已取消")
                    return
            
            print(f"清空现有目录 {base_dir}...")
            shutil.rmtree(base_dir)
            os.makedirs(base_dir, exist_ok=True)
        else:
            print(f"目录 {base_dir} 已存在，将继续添加文件")
            print(f"如需清空目录，请使用 clear_existing=True 参数")
    
    print(f"确保目录 {base_dir} 存在...")
    os.makedirs(base_dir, exist_ok=True)

   
    generated = 0  # 已成功生成的模型数

    # 使用 while 循环直到满足数量
    with tqdm(total=total_count, desc="生成训练模型") as pbar:
        while generated < total_count:
            try:
                # 生成单个CAD代码
                generator = CADCodeGenerator(1, 10)  # 限制操作数在1-10之间
                cq_code = generator.generate_cq_code()

                # 过滤空代码（loop_count=0的情况）
                if not cq_code.strip():
                    continue  # 空代码跳过，不计数

                # 保存文件序列
                file_count = save_cq_code_sequence(cq_code, base_dir, batch_size)
                generated += file_count  # 成功生成才计数
                pbar.update(file_count)  # 进度条按实际生成文件数更新

            except (ValueError, RuntimeError, AttributeError) as e:
                # 可恢复的错误
                print(f"\n生成文件时出错（可恢复）：{type(e).__name__}: {e}，跳过该文件")
                continue
            except KeyboardInterrupt:
                # 用户中断
                print(f"\n\n用户中断！已生成 {generated} 个模型")
                print(f"可以稍后继续生成（不会覆盖已有文件）")
                break
            except Exception as e:
                # 严重错误
                print(f"\n生成文件时发生严重错误：{type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                # 询问是否继续
                response = input("是否继续生成？(yes/no): ")
                if response.lower() != 'yes':
                    break
                continue

    print(f"生成完成！总模型数：{generated}，存放于 {base_dir}")


# 执行生成（注意：100万文件会占用大量磁盘空间，建议先测试小批量）
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='生成CAD训练数据')
    parser.add_argument('--count', type=int, default=5, 
                        help='生成的模型数量（默认100000）')
    parser.add_argument('--batch-size', type=int, default=10000,
                        help='每批文件数量（默认10000）')
    parser.add_argument('--clear', action='store_true',
                        help='清空现有目录（需要显式指定）')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("CAD训练数据生成")
    print("=" * 60)
    print(f"目标数量: {args.count}")
    print(f"批次大小: {args.batch_size}")
    print(f"清空现有: {'是' if args.clear else '否'}")
    print("=" * 60)
    print()
    
    generate_training_dataset(
        total_count=args.count,
        batch_size=args.batch_size,
        clear_existing=args
    )
