const PaperStorage = artifacts.require("PaperStorage");

module.exports = function(deployer) {
    deployer.deploy(PaperStorage);
};
