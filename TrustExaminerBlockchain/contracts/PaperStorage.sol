// SPDX-License-Identifier: MIT
pragma solidity ^0.5.16;

contract PaperStorage {
    struct Paper {
        uint id;
        string cid;  // IPFS CID
        string uploader;
        uint timestamp;
    }

    struct Download {  // NEW STRUCT
        uint id;
        uint paperId;  // ID of the downloaded paper
        string downloader;  // Username of the downloader
        uint timestamp;
    }

    mapping(uint => Paper) public papers;
    uint public paperCount;

    mapping(uint => Download) public downloads;  // NEW MAPPING
    uint public downloadCount;  // NEW COUNTER


    event PaperUploaded(uint id, string cid, string uploader, uint timestamp);
    event PaperDownloaded(uint id, uint paperId, string downloader, uint timestamp); // NEW EVENT


    function uploadPaper(string memory _cid, string memory _uploader) public {
        paperCount++;
        papers[paperCount] = Paper(paperCount, _cid, _uploader, block.timestamp);
        emit PaperUploaded(paperCount, _cid, _uploader, block.timestamp);
    }

    function getPaper(uint _id) public view returns (string memory, string memory, uint) {
        require(_id > 0 && _id <= paperCount, "Invalid paper ID");
        Paper memory p = papers[_id];
        return (p.cid, p.uploader, p.timestamp);
    }

    function recordDownload(uint _paperId, string memory _downloader) public { //NEW FUNCTION
        require(_paperId > 0 && _paperId <= paperCount, "Invalid paper ID");
        downloadCount++;
        downloads[downloadCount] = Download(downloadCount, _paperId, _downloader, block.timestamp);
        emit PaperDownloaded(downloadCount, _paperId, _downloader, block.timestamp);
    }
}