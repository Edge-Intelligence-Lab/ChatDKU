/**
 * Production Readiness Reporter
 * 
 * Industry standards for production deployment:
 * - Code coverage: ≥80% (good), ≥90% (excellent)
 * - Test success rate: 100% (all tests must pass)
 * - No critical failures in integration tests
 * - Type checking: Must pass
 */

class ProductionReadinessReporter {
  constructor(globalConfig, options = {}) {
    this.globalConfig = globalConfig;
    this.options = {
      minCoverage: 80, // minimum coverage percentage
      requireIntegrationTests: true,
      ...options
    };
    this.testResults = {
      total: 0,
      passed: 0,
      failed: 0,
      coverage: {},
      integrationTests: { passed: 0, failed: 0 }
    };
  }

  onRunStart() {
    console.log('\n🚀 Starting Production Readiness Assessment...\n');
  }

  onTestResult(test, testResult) {
    this.testResults.total += testResult.numPassingTests + testResult.numFailingTests;
    this.testResults.passed += testResult.numPassingTests;
    this.testResults.failed += testResult.numFailingTests;

    // Track integration tests separately
    if (test.path.includes('integration.') || test.path.includes('.integration.')) {
      this.testResults.integrationTests.passed += testResult.numPassingTests;
      this.testResults.integrationTests.failed += testResult.numFailingTests;
    }
  }

  onRunComplete(contexts, results) {
    console.log('\n📊 PRODUCTION READINESS ASSESSMENT');
    console.log('=====================================\n');

    // Calculate metrics
    const successRate = this.testResults.total > 0 ? (this.testResults.passed / this.testResults.total) * 100 : 0;
    const integrationSuccessRate = this.testResults.integrationTests.passed + this.testResults.integrationTests.failed > 0 
      ? (this.testResults.integrationTests.passed / (this.testResults.integrationTests.passed + this.testResults.integrationTests.failed)) * 100 
      : 100;

    // Get coverage data
    const coverage = results.coverageMap || {};
    const coverageMetrics = this.calculateCoverageMetrics(coverage);

    // Display results
    console.log('🔍 Test Results:');
    console.log(`   Total Tests: ${this.testResults.total}`);
    console.log(`   Passed: ${this.testResults.passed}`);
    console.log(`   Failed: ${this.testResults.failed}`);
    console.log(`   Success Rate: ${successRate.toFixed(2)}%`);
    
    if (this.testResults.integrationTests.passed + this.testResults.integrationTests.failed > 0) {
      console.log(`\n🔗 Integration Tests:`);
      console.log(`   Passed: ${this.testResults.integrationTests.passed}`);
      console.log(`   Failed: ${this.testResults.integrationTests.failed}`);
      console.log(`   Success Rate: ${integrationSuccessRate.toFixed(2)}%`);
    }

    console.log('\n📈 Code Coverage:');
    Object.entries(coverageMetrics).forEach(([metric, value]) => {
      const status = value >= this.options.minCoverage ? '✅' : value >= 60 ? '⚠️' : '❌';
      console.log(`   ${metric}: ${value.toFixed(2)}% ${status}`);
    });

    // Production readiness evaluation
    const evaluation = this.evaluateProductionReadiness(successRate, integrationSuccessRate, coverageMetrics);
    
    console.log('\n🎯 PRODUCTION DEPLOYMENT RECOMMENDATION:');
    console.log('==========================================');
    console.log(`   Overall Status: ${evaluation.status}`);
    console.log(`   Recommendation: ${evaluation.recommendation}`);
    
    if (evaluation.concerns.length > 0) {
      console.log('\n⚠️  Concerns:');
      evaluation.concerns.forEach(concern => console.log(`   • ${concern}`));
    }

    if (evaluation.strengths.length > 0) {
      console.log('\n✅ Strengths:');
      evaluation.strengths.forEach(strength => console.log(`   • ${strength}`));
    }

    console.log('\n' + '='.repeat(50));
    
    // Exit with appropriate code
    if (evaluation.canDeploy) {
      console.log('🚀 READY FOR PRODUCTION DEPLOYMENT');
      process.exit(0);
    } else {
      console.log('🚫 NOT READY FOR PRODUCTION DEPLOYMENT');
      process.exit(1);
    }
  }

  calculateCoverageMetrics(coverageMap) {
    const metrics = {
      'Lines': 0,
      'Functions': 0,
      'Branches': 0,
      'Statements': 0
    };

    if (!coverageMap || typeof coverageMap.getCoverageSummary !== 'function') {
      return metrics;
    }

    try {
      const summary = coverageMap.getCoverageSummary();
      
      if (summary.lines) {
        metrics.Lines = summary.lines.pct || 0;
      }
      if (summary.functions) {
        metrics.Functions = summary.functions.pct || 0;
      }
      if (summary.branches) {
        metrics.Branches = summary.branches.pct || 0;
      }
      if (summary.statements) {
        metrics.Statements = summary.statements.pct || 0;
      }
    } catch (error) {
      console.warn('Could not calculate coverage metrics:', error.message);
    }

    return metrics;
  }

  evaluateProductionReadiness(successRate, integrationSuccessRate, coverageMetrics) {
    const concerns = [];
    const strengths = [];
    let canDeploy = true;

    // Check test success rate (must be 100%)
    if (successRate < 100) {
      concerns.push(`Test success rate is ${successRate.toFixed(2)}% (must be 100%)`);
      canDeploy = false;
    } else {
      strengths.push('All tests are passing');
    }

    // Check integration tests
    if (this.options.requireIntegrationTests) {
      if (this.testResults.integrationTests.passed + this.testResults.integrationTests.failed === 0) {
        concerns.push('No integration tests found');
        canDeploy = false;
      } else if (integrationSuccessRate < 100) {
        concerns.push(`Integration test success rate is ${integrationSuccessRate.toFixed(2)}% (must be 100%)`);
        canDeploy = false;
      } else {
        strengths.push('All integration tests are passing');
      }
    }

    // Check coverage
    const avgCoverage = Object.values(coverageMetrics).reduce((a, b) => a + b, 0) / Object.values(coverageMetrics).length;
    
    Object.entries(coverageMetrics).forEach(([metric, value]) => {
      if (value < this.options.minCoverage) {
        concerns.push(`${metric} coverage is ${value.toFixed(2)}% (below ${this.options.minCoverage}% threshold)`);
        if (value < 60) canDeploy = false; // Critical threshold
      } else if (value >= 90) {
        strengths.push(`Excellent ${metric} coverage (${value.toFixed(2)}%)`);
      }
    });

    // Overall coverage assessment
    if (avgCoverage >= this.options.minCoverage) {
      strengths.push(`Overall code coverage meets standards (${avgCoverage.toFixed(2)}%)`);
    } else {
      concerns.push(`Overall code coverage is below threshold (${avgCoverage.toFixed(2)}% < ${this.options.minCoverage}%)`);
    }

    // Determine status
    let status, recommendation;
    if (canDeploy && avgCoverage >= 90) {
      status = '🟢 EXCELLENT';
      recommendation = 'Highly recommended for production deployment';
    } else if (canDeploy && avgCoverage >= this.options.minCoverage) {
      status = '🟡 READY';
      recommendation = 'Ready for production deployment with acceptable quality';
    } else if (canDeploy) {
      status = '🟡 MARGINAL';
      recommendation = 'Can deploy to production but consider improving coverage';
    } else {
      status = '🔴 NOT READY';
      recommendation = 'Do not deploy to production - critical issues must be addressed';
    }

    return {
      canDeploy,
      status,
      recommendation,
      concerns,
      strengths
    };
  }
}

module.exports = ProductionReadinessReporter;