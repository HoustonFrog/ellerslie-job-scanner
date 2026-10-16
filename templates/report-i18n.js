const messages = {
  en: {
    brand:'Ellerslie Jobs', navContext:'Accounting & finance · Auckland', eyebrow:'OPPORTUNITIES NEAR ELLERSLIE',
    heroPrimary:'Finance roles.', heroSecondary:'Closer to home.',
    heroDescription:'Explore accounting and finance opportunities near Ellerslie School, with recommendations tailored to your experience.',
    opportunities:'opportunities', opportunity:'opportunity', newThisScan:'New this scan', newStat:'new this scan', nearby:'nearby',
    sortBy:'Sort by', bestMatch:'Best match', mostRecent:'Most recent', salarySort:'Salary · annual first',
    allJobs:'All jobs', nearbyAreas:'Ellerslie & nearby', otherAreas:'Other areas', newOnly:'New this scan only',
    clearFilters:'Clear filters', searchPlaceholder:'Search jobs, companies or locations', searchAria:'Search jobs, companies or locations',
    locationFilter:'Location', findAJob:'Find a job', jobsRegion:'Job opportunities', nearbyScope:'Ellerslie, Greenlane & Remuera', allAreas:'All areas',
    noResults:'No matching opportunities.', noResultsHint:'Try another keyword or clear your filters to see all jobs.', showAllJobs:'Show all jobs',
    salarySortNote:'Annual pay uses the lower advertised amount, or the advertised maximum for “up to” offers. Hourly rates follow. Check FTE and part-time terms in each listing.',
    reportGenerated:'Report generated', nzTime:'NZ time', sources:'sources', appearance:'Appearance', system:'System', light:'Light', dark:'Dark',
    recommendation:'Why this role', match:'Match', salaryUndisclosed:'Salary not disclosed', estimated:'Estimated',
    viewJob:'View job', readDetails:'Read details', hideDetails:'Hide details', jobDescription:'Original job description (English)',
    matchBreakdown:'Match breakdown', companyCareers:'Company careers', descriptionMissing:'View the original listing for the full job description.',
    skipJobs:'Skip to jobs', mainNavigation:'Main navigation', reportOverview:'Report overview', noScript:'All opportunities are shown. Enable JavaScript to switch languages, search, filter and sort.'
  },
  zh: {
    brand:'Ellerslie 求职', navContext:'会计与财务 · 奥克兰', eyebrow:'ELLERSLIE 周边职位',
    heroPrimary:'财务机会。', heroSecondary:'就在附近。',
    heroDescription:'寻找 Ellerslie School 周边的会计与财务工作，结合你的经历，一眼了解职位内容与匹配理由。',
    opportunities:'个职位', opportunity:'个职位', newThisScan:'本次新增', newStat:'本次新增', nearby:'附近职位',
    sortBy:'排序', bestMatch:'匹配度优先', mostRecent:'最近发布', salarySort:'薪资优先 · 年薪在前',
    allJobs:'全部职位', nearbyAreas:'Ellerslie 及附近', otherAreas:'其他地区', newOnly:'仅看本次新增',
    clearFilters:'清除筛选', searchPlaceholder:'搜索职位、公司或地点', searchAria:'搜索职位、公司或地点',
    locationFilter:'工作地区', findAJob:'查找职位', jobsRegion:'职位列表', nearbyScope:'Ellerslie、Greenlane 及 Remuera', allAreas:'全部地区',
    noResults:'没有符合条件的职位。', noResultsHint:'试试其他关键词，或清除筛选查看全部职位。', showAllJobs:'查看全部职位',
    salarySortNote:'年薪按披露区间的下限排序；“最高可达”按披露上限排序。时薪排在年薪之后。请留意职位原文中的全职折算及兼职薪资口径。',
    reportGenerated:'报告生成于', nzTime:'新西兰时间', sources:'个来源', appearance:'外观', system:'跟随系统', light:'浅色', dark:'深色',
    recommendation:'推荐理由', match:'匹配度', salaryUndisclosed:'薪资未披露', estimated:'估算',
    viewJob:'查看职位', readDetails:'查看详情', hideDetails:'收起详情', jobDescription:'招聘正文（英文原文）',
    matchBreakdown:'查看评分明细', companyCareers:'公司招聘官网', descriptionMissing:'请打开职位原文查看完整招聘说明。',
    skipJobs:'跳转到职位列表', mainNavigation:'主导航', reportOverview:'职位概览', noScript:'已展示全部职位。启用 JavaScript 后可切换语言、搜索、筛选和排序。'
  }
};
let language = 'zh';
function t(key) { return messages[language][key] || messages.en[key] || key; }
function localizeDocument() {
  document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en-NZ';
  document.querySelectorAll('[data-i18n]').forEach(function(el) { el.textContent=t(el.dataset.i18n); });
  document.querySelectorAll('[data-en][data-zh]').forEach(function(el) { el.textContent=language === 'zh' ? el.dataset.zh : el.dataset.en; });
  document.querySelectorAll('[data-i18n-aria]').forEach(function(el) { el.setAttribute('aria-label',t(el.dataset.i18nAria)); });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(function(el) { el.setAttribute('placeholder',t(el.dataset.i18nPlaceholder)); });
  document.querySelectorAll('.recommendation').forEach(function(el) { el.lang=language === 'zh' ? 'zh-CN' : 'en'; });
  document.querySelectorAll('[data-language]').forEach(function(el) { el.setAttribute('aria-pressed',String(el.dataset.language===language)); });
  const reportDate = document.querySelector('[data-report-date]');
  reportDate.textContent = new Intl.DateTimeFormat(language === 'zh' ? 'zh-CN' : 'en-NZ',{year:'numeric',month:'long',day:'numeric',timeZone:'Pacific/Auckland'}).format(new Date(reportDate.dateTime+'T00:00:00Z'));
  document.title=t('brand')+' — '+reportDate.textContent;
}
