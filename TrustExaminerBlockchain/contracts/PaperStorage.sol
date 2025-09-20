// SPDX-License-Identifier: MIT
pragma solidity ^0.5.16;

contract PaperStorage {
    struct Paper {
        uint id;
        string cid;         // IPFS CID
        string filename;    // Filename of the paper
        string uploader;
        uint timestamp;
    }

    struct Download {
        uint id;
        uint paperId;
        string filename;     // Filename of the paper downloaded
        string downloader;
        uint timestamp;
    }

    mapping(uint => Paper) public papers;
    uint public paperCount;

    mapping(uint => Download) public downloads;
    uint public downloadCount;

    event PaperUploaded(uint id, string cid, string filename, string uploader, uint timestamp); // Added filename
    event PaperDownloaded(uint id, uint paperId, string filename, string downloader, uint timestamp); // Added filename and downloader


    function uploadPaper(string memory _cid, string memory _filename, string memory _uploader) public { // Added _filename
        paperCount++;
        papers[paperCount] = Paper(paperCount, _cid, _filename, _uploader, block.timestamp); // Store filename
        emit PaperUploaded(paperCount, _cid, _filename, _uploader, block.timestamp); // Emit filename
    }

    function getPaper(uint _id) public view returns (string memory, string memory, uint) {
        require(_id > 0 && _id <= paperCount, "Invalid paper ID");
        Paper memory p = papers[_id];
        return (p.cid, p.uploader, p.timestamp);
    }

    function recordDownload(uint _paperId, string memory _filename, string memory _downloader) public { // Added _filename
        require(_paperId > 0 && _paperId <= paperCount, "Invalid paper ID");
        downloadCount++;
        downloads[downloadCount] = Download(downloadCount, _paperId, _filename, _downloader, block.timestamp); // Store filename and downloader
        emit PaperDownloaded(downloadCount, _paperId, _filename, _downloader, block.timestamp); // Emit filename and downloader
    }
}