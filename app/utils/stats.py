from datetime import datetime, timedelta
from app.utils.logging import log

def clean_expired_stats(api_call_stats):
    """清理过期统计数据的函数"""
    now = datetime.now()
    
    # 清理24小时前的数据
    # 清理总调用次数
    for hour_key in list(api_call_stats['last_24h']['total'].keys()):
        try:
            hour_time = datetime.strptime(hour_key, '%Y-%m-%d %H:00')
            if (now - hour_time).total_seconds() > 24 * 3600:  # 超过24小时
                del api_call_stats['last_24h']['total'][hour_key]
        except ValueError:
            # 如果键格式不正确，直接删除
            del api_call_stats['last_24h']['total'][hour_key]
    
    # 清理按端点和模型分类的数据
    for endpoint in list(api_call_stats['last_24h']['by_endpoint'].keys()):
        if not isinstance(api_call_stats['last_24h']['by_endpoint'][endpoint], dict):
            del api_call_stats['last_24h']['by_endpoint'][endpoint]
            continue
            
        for model in list(api_call_stats['last_24h']['by_endpoint'][endpoint].keys()):
            if not isinstance(api_call_stats['last_24h']['by_endpoint'][endpoint][model], dict):
                del api_call_stats['last_24h']['by_endpoint'][endpoint][model]
                continue
                
            for hour_key in list(api_call_stats['last_24h']['by_endpoint'][endpoint][model].keys()):
                try:
                    hour_time = datetime.strptime(hour_key, '%Y-%m-%d %H:00')
                    if (now - hour_time).total_seconds() > 24 * 3600:  # 超过24小时
                        del api_call_stats['last_24h']['by_endpoint'][endpoint][model][hour_key]
                except ValueError:
                    # 如果键格式不正确，直接删除
                    del api_call_stats['last_24h']['by_endpoint'][endpoint][model][hour_key]
    
    # 清理一小时前的小时统计数据
    one_hour_ago = now - timedelta(hours=1)
    # 清理总调用次数
    for hour_key in list(api_call_stats['hourly']['total'].keys()):
        try:
            hour_time = datetime.strptime(hour_key, '%Y-%m-%d %H:00')
            if hour_time < one_hour_ago:
                del api_call_stats['hourly']['total'][hour_key]
        except ValueError:
            # 如果键格式不正确，直接删除
            del api_call_stats['hourly']['total'][hour_key]
    
    # 清理按端点和模型分类的数据
    for endpoint in list(api_call_stats['hourly']['by_endpoint'].keys()):
        if not isinstance(api_call_stats['hourly']['by_endpoint'][endpoint], dict):
            del api_call_stats['hourly']['by_endpoint'][endpoint]
            continue
            
        for model in list(api_call_stats['hourly']['by_endpoint'][endpoint].keys()):
            if not isinstance(api_call_stats['hourly']['by_endpoint'][endpoint][model], dict):
                del api_call_stats['hourly']['by_endpoint'][endpoint][model]
                continue
                
            for hour_key in list(api_call_stats['hourly']['by_endpoint'][endpoint][model].keys()):
                try:
                    hour_time = datetime.strptime(hour_key, '%Y-%m-%d %H:00')
                    if hour_time < one_hour_ago:
                        del api_call_stats['hourly']['by_endpoint'][endpoint][model][hour_key]
                except ValueError:
                    # 如果键格式不正确，直接删除
                    del api_call_stats['hourly']['by_endpoint'][endpoint][model][hour_key]
    
    # 清理一分钟前的分钟统计数据
    one_minute_ago = now - timedelta(minutes=1)
    # 清理总调用次数
    for minute_key in list(api_call_stats['minute']['total'].keys()):
        try:
            minute_time = datetime.strptime(minute_key, '%Y-%m-%d %H:%M')
            if minute_time < one_minute_ago:
                del api_call_stats['minute']['total'][minute_key]
        except ValueError:
            # 如果键格式不正确，直接删除
            del api_call_stats['minute']['total'][minute_key]
    
    # 清理按端点和模型分类的数据
    for endpoint in list(api_call_stats['minute']['by_endpoint'].keys()):
        if not isinstance(api_call_stats['minute']['by_endpoint'][endpoint], dict):
            del api_call_stats['minute']['by_endpoint'][endpoint]
            continue
            
        for model in list(api_call_stats['minute']['by_endpoint'][endpoint].keys()):
            if not isinstance(api_call_stats['minute']['by_endpoint'][endpoint][model], dict):
                del api_call_stats['minute']['by_endpoint'][endpoint][model]
                continue
                
            for minute_key in list(api_call_stats['minute']['by_endpoint'][endpoint][model].keys()):
                try:
                    minute_time = datetime.strptime(minute_key, '%Y-%m-%d %H:%M')
                    if minute_time < one_minute_ago:
                        del api_call_stats['minute']['by_endpoint'][endpoint][model][minute_key]
                except ValueError:
                    # 如果键格式不正确，直接删除
                    del api_call_stats['minute']['by_endpoint'][endpoint][model][minute_key]

def update_api_call_stats(api_call_stats, endpoint=None, model=None):
    """
    更新API调用统计的函数
    
    参数:
    - api_call_stats: 统计数据字典
    - endpoint: API端点,为None则只更新总调用次数
    - model: 模型名称,与endpoint一起使用来分类统计数据
    """
    now = datetime.now()
    hour_key = now.strftime('%Y-%m-%d %H:00')
    minute_key = now.strftime('%Y-%m-%d %H:%M')
    
    # 检查并清理过期统计
    clean_expired_stats(api_call_stats)
    
    # 初始化总调用次数键（如果不存在）
    if hour_key not in api_call_stats['last_24h']['total']:
        api_call_stats['last_24h']['total'][hour_key] = 0
    if hour_key not in api_call_stats['hourly']['total']:
        api_call_stats['hourly']['total'][hour_key] = 0
    if minute_key not in api_call_stats['minute']['total']:
        api_call_stats['minute']['total'][minute_key] = 0
    
    # 更新总调用次数统计
    api_call_stats['last_24h']['total'][hour_key] += 1
    api_call_stats['hourly']['total'][hour_key] += 1
    api_call_stats['minute']['total'][minute_key] += 1
    
    # 如果提供了端点，更新按端点分类的统计
    if endpoint and model:
        # 确保端点字典存在
        for period in ['last_24h', 'hourly', 'minute']:
            if endpoint not in api_call_stats[period]['by_endpoint']:
                api_call_stats[period]['by_endpoint'][endpoint] = {}
            
            if model not in api_call_stats[period]['by_endpoint'][endpoint]:
                api_call_stats[period]['by_endpoint'][endpoint][model] = {}
        
        # 初始化端点和模型特定的时间键（如果不存在）
        if hour_key not in api_call_stats['last_24h']['by_endpoint'][endpoint][model]:
            api_call_stats['last_24h']['by_endpoint'][endpoint][model][hour_key] = 0
            
        if hour_key not in api_call_stats['hourly']['by_endpoint'][endpoint][model]:
            api_call_stats['hourly']['by_endpoint'][endpoint][model][hour_key] = 0
            
        if minute_key not in api_call_stats['minute']['by_endpoint'][endpoint][model]:
            api_call_stats['minute']['by_endpoint'][endpoint][model][minute_key] = 0
        
        # 更新端点特定的统计
        if model is not None:
            api_call_stats['last_24h']['by_endpoint'][endpoint][model][hour_key] += 1
            api_call_stats['hourly']['by_endpoint'][endpoint][model][hour_key] += 1
            api_call_stats['minute']['by_endpoint'][endpoint][model][minute_key] += 1
    
    # 计算总调用次数
    total_24h = sum(api_call_stats['last_24h']['total'].values())
    total_hourly = sum(api_call_stats['hourly']['total'].values())
    total_minute = sum(api_call_stats['minute']['total'].values())
    
    log_message = "API调用统计已更新: 24小时=%s, 1小时=%s, 1分钟=%s" % (
        total_24h, total_hourly, total_minute
    )
    
    # 如果提供了端点和模型，添加端点特定的统计信息
    if endpoint and model is not None:
        try:
            endpoint_24h = sum(api_call_stats['last_24h']['by_endpoint'][endpoint][model].values())
            endpoint_hourly = sum(api_call_stats['hourly']['by_endpoint'][endpoint][model].values())
            endpoint_minute = sum(api_call_stats['minute']['by_endpoint'][endpoint][model].values())
            
            log_message += " | 端点 '%s' 模型 '%s': 24小时=%s, 1小时=%s, 1分钟=%s" % (
                endpoint[:8], model[:8], endpoint_24h, endpoint_hourly, endpoint_minute
            )
        except (KeyError, TypeError):
            # 如果统计数据结构中缺少某些键，记录基本信息
            log_message += " | 端点 '%s' 模型 '%s': 统计数据不完整" % (
                endpoint[:8], model[:8]
            )
    else:
        log_message += " | 端点 '%s' 模型 '%s': 统计数据不完整" 
    
    log('info', log_message)