/**
 * Composition root for the categories resource.
 */

const { DrizzleCategoryRepository } = require('./adapters/sql');
const { buildItemsRepository } = require('../items/depts');
const { CategoriesService } = require('./service');

function buildCategoryRepository(db) {
  return new DrizzleCategoryRepository(db);
}

function buildCategoriesService(db) {
  return new CategoriesService(buildCategoryRepository(db), buildItemsRepository(db));
}

module.exports = { buildCategoryRepository, buildCategoriesService };
