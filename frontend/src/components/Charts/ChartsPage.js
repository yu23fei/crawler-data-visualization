import React, { useState, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import { dataAPI } from '../../utils/api';

const StatCard = ({ title, value, color }) => (
    <div style={{ ...styles.card, borderLeft: `4px solid ${color}` }}>
        <div style={styles.cardTitle}>{title}</div>
        <div style={{ ...styles.cardValue, color }}>{value}</div>
    </div>
);

const ChartCard = ({ title, children, height = 400 }) => (
    <div style={styles.chartCard}>
        <h3 style={styles.chartTitle}>{title}</h3>
        <div style={{ height }}>{children}</div>
    </div>
);

const COLORS = ['#1890ff', '#52c41a', '#fa8c16', '#722ed1', '#13c2c2', '#eb2f96', '#f5222d', '#faad14', '#a0d911', '#2f54eb'];

const ChartsPage = () => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const result = await dataAPI.getAnalysis();
                if (result.code === 200) {
                    setData(result.data);
                } else {
                    setError(result.msg || '获取数据失败');
                }
            } catch (err) {
                setError('网络错误，请检查后端服务是否启动');
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    if (loading) return <div style={styles.loading}>加载中...</div>;
    if (error) return <div style={styles.error}>{error}</div>;
    if (!data) return <div style={styles.error}>暂无数据</div>;

    // 城市分布柱状图
    const cityOption = {
        tooltip: { trigger: 'axis' },
        xAxis: {
            type: 'category',
            data: data.city_distribution.map(i => i.name),
            axisLabel: { rotate: 45 }
        },
        yAxis: { type: 'value', name: '岗位数量' },
        series: [{
            data: data.city_distribution.map(i => i.value),
            type: 'bar',
            itemStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#1890ff' }, { offset: 1, color: '#69c0ff' }] } }
        }],
        grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true }
    };

    // 学历分布环形图
    const educationOption = {
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { orient: 'vertical', left: 'left', top: 'center' },
        series: [{
            type: 'pie', radius: ['40%', '70%'],
            center: ['55%', '50%'],
            itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
            label: { show: true, formatter: '{b}\n{d}%' },
            data: data.education_distribution.map(i => ({ name: i.name, value: i.value }))
        }]
    };

    // 薪资分布柱状图
    const salaryOption = {
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: data.salary_distribution.map(i => i.name || '面议') },
        yAxis: { type: 'value', name: '岗位数量' },
        series: [{
            data: data.salary_distribution.map(i => i.value),
            type: 'bar',
            itemStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#52c41a' }, { offset: 1, color: '#95de64' }] } }
        }],
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true }
    };

    // 经验分布饼图
    const experienceOption = {
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { orient: 'vertical', left: 'left', top: 'center' },
        series: [{
            type: 'pie', radius: '65%',
            center: ['55%', '50%'],
            data: data.experience_distribution.map(i => ({ name: i.name || '未知', value: i.value })),
            emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' } }
        }]
    };

    // 公司规模饼图
    const companySizeOption = {
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { orient: 'vertical', left: 'left', top: 'center' },
        series: [{
            type: 'pie', radius: '65%',
            center: ['55%', '50%'],
            data: data.company_size_distribution.map(i => ({ name: i.name || '未知', value: i.value })),
            emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' } }
        }]
    };

    // 行业分布柱状图
    const industryOption = {
        tooltip: { trigger: 'axis' },
        xAxis: {
            type: 'category',
            data: data.industry_distribution.map(i => i.name || '未知'),
            axisLabel: { rotate: 45 }
        },
        yAxis: { type: 'value', name: '岗位数量' },
        series: [{
            data: data.industry_distribution.map(i => i.value),
            type: 'bar',
            itemStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#fa8c16' }, { offset: 1, color: '#ffc53d' }] } }
        }],
        grid: { left: '3%', right: '4%', bottom: '20%', containLabel: true }
    };

    // 城市等级平均薪资柱状图
    const cityTierSalaryOption = {
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: data.city_tier_salary.map(i => i.name) },
        yAxis: { type: 'value', name: '平均薪资（元）' },
        series: [{
            data: data.city_tier_salary.map(i => i.value),
            type: 'bar',
            itemStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#722ed1' }, { offset: 1, color: '#b37feb' }] } }
        }],
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true }
    };

    // 福利评分分布柱状图
    const benefitOption = {
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: data.benefit_score_distribution.map(i => i.name) },
        yAxis: { type: 'value', name: '岗位数量' },
        series: [{
            data: data.benefit_score_distribution.map(i => i.value),
            type: 'bar',
            itemStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#13c2c2' }, { offset: 1, color: '#5cdbd3' }] } }
        }],
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true }
    };

    // 公司性质分布饼图
    const companyTypeOption = {
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { orient: 'vertical', left: 'left', top: 'center', type: 'scroll' },
        series: [{
            type: 'pie', radius: ['35%', '65%'],
            center: ['60%', '50%'],
            data: data.company_type_distribution.map(i => ({ name: i.name || '未知', value: i.value })),
            emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' } }
        }]
    };

    // 工作类型分布饼图
    const workTypeOption = {
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { orient: 'vertical', left: 'left', top: 'center' },
        series: [{
            type: 'pie', radius: '65%',
            center: ['55%', '50%'],
            roseType: 'radius',
            data: data.work_type_distribution.map(i => ({ name: i.name || '未知', value: i.value })),
            itemStyle: { borderRadius: 5 }
        }]
    };

    // 经验-薪资关系柱状图
    const experienceSalaryOption = {
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: data.experience_salary.map(i => i.name) },
        yAxis: { type: 'value', name: '平均薪资（元）' },
        series: [{
            data: data.experience_salary.map(i => i.value),
            type: 'bar',
            barWidth: '50%',
            itemStyle: {
                color: function(params) {
                    var colorList = ['#91d5ff', '#69c0ff', '#40a9ff', '#1890ff', '#096dd9'];
                    return colorList[params.dataIndex % colorList.length];
                }
            },
            label: { show: true, position: 'top', formatter: '{c}' }
        }],
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true }
    };

    // 城市等级分布饼图
    const cityTierOption = {
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { orient: 'vertical', left: 'left', top: 'center' },
        series: [{
            type: 'pie', radius: '65%',
            center: ['55%', '50%'],
            data: data.city_tier_distribution.map(i => ({ name: i.name || '未知', value: i.value })),
            emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' } }
        }]
    };

    return (
        <div style={styles.container}>
            <h2 style={styles.pageTitle}>招聘数据可视化分析</h2>

            <div style={styles.cardContainer}>
                <StatCard title="总岗位数" value={data.overview.total_jobs} color="#1890ff" />
                <StatCard title="平均薪资" value={`¥${data.overview.avg_salary}`} color="#52c41a" />
                <StatCard title="涉及城市" value={data.overview.total_cities} color="#fa8c16" />
                <StatCard title="招聘企业" value={data.overview.total_companies} color="#722ed1" />
            </div>

            <div style={styles.chartGrid}>
                <ChartCard title="城市分布 TOP15">
                    <ReactECharts option={cityOption} style={{ height: '100%' }} />
                </ChartCard>

                <ChartCard title="城市等级分布">
                    <ReactECharts option={cityTierOption} style={{ height: '100%' }} />
                </ChartCard>

                <ChartCard title="学历要求分布">
                    <ReactECharts option={educationOption} style={{ height: '100%' }} />
                </ChartCard>

                <ChartCard title="薪资范围分布">
                    <ReactECharts option={salaryOption} style={{ height: '100%' }} />
                </ChartCard>

                <ChartCard title="工作经验要求">
                    <ReactECharts option={experienceOption} style={{ height: '100%' }} />
                </ChartCard>

                <ChartCard title="经验与薪资关系">
                    <ReactECharts option={experienceSalaryOption} style={{ height: '100%' }} />
                </ChartCard>

                <ChartCard title="公司规模分布">
                    <ReactECharts option={companySizeOption} style={{ height: '100%' }} />
                </ChartCard>

                <ChartCard title="公司性质分布">
                    <ReactECharts option={companyTypeOption} style={{ height: '100%' }} />
                </ChartCard>

                <ChartCard title="行业分布 TOP15">
                    <ReactECharts option={industryOption} style={{ height: '100%' }} />
                </ChartCard>

                <ChartCard title="工作类型分布">
                    <ReactECharts option={workTypeOption} style={{ height: '100%' }} />
                </ChartCard>

                <ChartCard title="城市等级平均薪资">
                    <ReactECharts option={cityTierSalaryOption} style={{ height: '100%' }} />
                </ChartCard>

                <ChartCard title="福利评分分布">
                    <ReactECharts option={benefitOption} style={{ height: '100%' }} />
                </ChartCard>
            </div>
        </div>
    );
};

const styles = {
    container: { padding: '20px' },
    pageTitle: { fontSize: '24px', fontWeight: 'bold', marginBottom: '24px', color: '#262626' },
    loading: { textAlign: 'center', padding: '50px', fontSize: '16px', color: '#999' },
    error: { textAlign: 'center', padding: '50px', fontSize: '16px', color: '#ff4d4f' },
    cardContainer: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px', marginBottom: '24px' },
    card: { background: '#fff', borderRadius: '8px', padding: '20px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' },
    cardTitle: { fontSize: '14px', color: '#999', marginBottom: '8px' },
    cardValue: { fontSize: '28px', fontWeight: 'bold' },
    chartGrid: { display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '20px' },
    chartCard: { background: '#fff', borderRadius: '8px', padding: '20px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' },
    chartTitle: { fontSize: '16px', fontWeight: '600', marginBottom: '16px', color: '#262626' }
};

export default ChartsPage;
