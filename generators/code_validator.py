"""
独立的代码验证模块，用于在隔离环境中执行和验证生成的CAD代码
"""
import sys
import subprocess
import tempfile
import os


def validate_code_in_subprocess(code_to_validate):
    """
    在独立的子进程中执行代码并返回体积
    
    Args:
        code_to_validate: 要验证的完整代码字符串
        
    Returns:
        tuple: (success: bool, volume: float or None, error_message: str or None)
    """
    # 获取项目根目录路径
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    # 创建临时文件来存储要执行的代码
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        # 写入验证代码
        validation_code = f"""
import sys
import os

# 添加项目根目录到sys.path
project_root = r'{project_root}'
if project_root not in sys.path:
    sys.path.insert(0, project_root)

{code_to_validate}

# 计算体积并输出
try:
    if 'result' in locals():
        current_solid = result.val()
        if hasattr(current_solid, 'Volume'):
            volume = current_solid.Volume()
            print(f"VOLUME:{{volume}}")
        else:
            print("ERROR:实体不支持Volume()方法")
    else:
        print("ERROR:未生成有效的实体result")
except Exception as e:
    import traceback
    print(f"ERROR:{{type(e).__name__}}: {{e}}")
    traceback.print_exc()
"""
        f.write(validation_code)
        temp_file_path = f.name
    
    process = None
    try:
        # 构建环境变量，包含当前的PYTHONPATH
        env = os.environ.copy()
        current_pythonpath = env.get('PYTHONPATH', '')
        all_paths = [project_root] + sys.path
        if current_pythonpath:
            all_paths.append(current_pythonpath)
        env['PYTHONPATH'] = os.pathsep.join(all_paths)
        
        # 在子进程中执行代码
        result = subprocess.run(
            [sys.executable, temp_file_path],
            capture_output=True,
            text=True,
            timeout=10,  # 10秒超时
            env=env
        )
        
        # 解析输出
        output = result.stdout.strip()
        
        if output.startswith("VOLUME:"):
            try:
                volume = float(output.split("VOLUME:")[1])
                return True, volume, None
            except ValueError:
                return False, None, f"无法解析体积值: {output}"
        elif output.startswith("ERROR:"):
            error_msg = output.split("ERROR:")[1]
            return False, None, error_msg
        else:
            # 检查stderr
            if result.stderr:
                return False, None, f"执行错误: {result.stderr}"
            return False, None, f"未知输出: {output}"
            
    except subprocess.TimeoutExpired as e:
        # 超时时，subprocess.run已经终止了子进程
        # 但我们可以确保清理
        if e.process:
            try:
                e.process.kill()  # 确保进程被终止
                e.process.wait()  # 等待进程完全退出
            except:
                pass
        return False, None, "代码执行超时（子进程已终止）"
    except Exception as e:
        return False, None, f"子进程执行失败: {type(e).__name__}: {e}"
    finally:
        # 清理临时文件
        try:
            os.unlink(temp_file_path)
        except:
            pass


def validate_code_volume_change(code_to_validate, last_volume=None, relative_threshold=0.001):
    """
    验证代码并判断体积是否发生变化
    
    Args:
        code_to_validate: 要验证的完整代码
        last_volume: 上一次的体积值
        relative_threshold: 相对变化阈值（默认0.1%）
        
    Returns:
        tuple: (is_valid: bool, is_changed: bool, current_volume: float or None, error_message: str or None)
    """
    success, current_volume, error_msg = validate_code_in_subprocess(code_to_validate)
    
    if not success:
        return False, False, None, error_msg
    
    # 判断体积是否变化
    if last_volume is None:
        # 首次验证，认为有变化
        is_changed = True
    else:
        # 使用相对误差判断
        if abs(last_volume) < 1e-10:
            # 上一次体积接近零，使用绝对误差
            is_changed = abs(current_volume) > 1e-6
        else:
            # 使用相对误差
            relative_change = abs(current_volume - last_volume) / abs(last_volume)
            is_changed = relative_change > relative_threshold
    
    return True, is_changed, current_volume, None
