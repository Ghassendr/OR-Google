-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Apr 02, 2026 at 12:11 AM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.1.25

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `gestion_examens`
--

-- --------------------------------------------------------

--
-- Table structure for table `proffer`
--

CREATE TABLE `proffer` (
  `id_proffer` int(11) NOT NULL,
  `nom_professeur` varchar(150) NOT NULL,
  `grade` varchar(100) DEFAULT NULL,
  `charge_surv` int(11) DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `proffer`
--

INSERT INTO `proffer` (`id_proffer`, `nom_professeur`, `grade`, `charge_surv`) VALUES
(1, 'BEN SALAH Mohamed', 'Maître Assistant', 5),
(2, 'ELOURAGINI Salem', 'Professeur 5,5 HC', 5),
(3, 'KOUKA Neji', 'Cont docteur 9,5 HTD', 8),
(4, 'BEN NACEUR Ferdaws', 'Cont docteur 9,5 HTD', 4),
(5, 'HEDHILI Lamia', 'Assistant', 5),
(6, 'HENTATI Nesrine', 'Maître Assistant', 4),
(7, 'MABROUK Hanene', 'Maître Assistant', 4),
(8, 'EL MAY Sana', 'Maître Assistant', 4),
(9, 'ILJI Samia', NULL, 0),
(10, 'CHOUIGUI Ajmi', 'Maître Assistant', 6),
(11, 'SASSI Latifa', 'Maître Assistant', 5),
(12, 'BEN HAMMADI KACEM Iyadh', 'Assistant', 4),
(13, 'BELHADJ TAHER Ahmed', 'Maître Assistant', 5),
(14, 'MAHMOUDI Nejib', 'Maître Assistant', 5),
(15, 'MALEK Jihene', 'Professeur 5,5 HC', 10),
(16, 'MAHMOUD Rihem', 'Cont docteur 9,5 HTD', 5),
(17, 'ZAALANI Nadhem', 'Maître Assistant', 5),
(18, 'ADOUANI Ines', 'Maître Assistant', 6),
(19, 'KHALFALLAH Sofiane', 'Maître Assistant', 7),
(20, 'KALLEL Sami', 'Professeur 5,5 HC', 5),
(21, 'HASSEN Mohamed', 'Maître de Conférences', 2),
(22, 'BOUASKER Souad', 'Maître Assistant', 5),
(23, 'KARMANI Sourour', 'Maître Assistant', 4),
(24, 'KALLEL Nabil', 'Professeur 5,5 HC', 5),
(25, 'AMMAR Emna', NULL, 0),
(26, 'BOUFADEN Tarek', 'Professeur 5,5 HC', 6),
(27, 'CHEBBI Afef', 'Maître Assistant', 5),
(28, 'OUNI Faten', 'Assistant', 7),
(29, 'NACEUR Amel', 'Maître Assistant', 7),
(30, 'FATNASSI Ons', 'Cont docteur 9,5 HTD', 0),
(31, 'SLIMENE Ons', NULL, 0),
(32, 'MAZHOUDA Kamel', 'Maître de Conférences', 5),
(33, 'BEN CHRIFA Ali', 'Maître Assistant', 5),
(34, 'SOUANI Chokri', 'Professeur 5,5 HC', 5),
(35, 'HATTAB ABROUGUI Hanen', 'Maître Assistant', 5),
(36, 'ZOUARI Slim', 'Maître Assistant', 5),
(37, 'TRIKI GARGOURI Dorra', 'Maître Assistant', 9),
(38, 'MOULAHI Samir', 'Maître Assistant', 4),
(39, 'FARHAT Habib', 'Maître de Conférences', 1),
(40, 'BENNOUR Fadhel', 'Maître Assistant', 2),
(41, 'BELGHITH Nader', 'Maître Assistant', 4),
(42, 'TARRACH Fredj', 'Maître Assistant', 5),
(43, 'ZERGANE Amel', 'Maître Assistant', 7),
(44, 'SAIDI Faouzi', 'Professeur 5,5 HC', 5),
(45, 'BLAYECH Hayfa', 'Cont docteur 9,5 HTD', 8),
(46, 'BARIKA KTATA Farah', 'Maître Assistant', 5),
(47, 'HAMMAMI Souad', 'Cont docteur 9,5 HTD', 5),
(48, 'BHAR Jamila', 'Maître Assistant', 8),
(49, 'MILI Maher', 'Professeur 5,5 HC', 5),
(50, 'ELLOUZE Imen', 'Maître de Conférences-Vac', 6),
(51, 'LEFFET Samia', 'Maître Assistant', 5),
(52, 'FOURATI Farah', 'Maître Assistant', 7),
(53, 'ABDELKEFI Mahdi', 'Assistant', 8),
(54, 'ZAABOUB Wala', 'Cont docteur 9,5 HTD', 4),
(55, 'JABLI Nizar', 'Maître Assistant', 5),
(56, 'BANNOUR Sana', 'Maître Assistant', 3),
(57, 'HSAIRI Nizar', 'Assistant', 4),
(58, 'BEN HADJ SALAH Hend', 'Maître Assistant', 8),
(59, 'CHAOUACH Helmi', 'Maître Assistant', 8),
(60, 'BEN MAKHLOUF Aicha', 'Maître Assistant', 5),
(61, 'ZAABOUB Nihel', 'Cont docteur 9,5 HTD', 11),
(62, 'HEMAYED Mariem', 'Contrat Expert  5 HTD', 3),
(63, 'CHAOUCH Najla', 'PP Emérité- Capes14  H TD', 12),
(64, 'FARJALLAH Mohamed', 'Maître Assistant', 9),
(65, 'MELLOULI MOALLA Dorra', 'Maître Assistant', 5),
(66, 'BELHADJ Rachida', 'Assistant', 6),
(67, 'TAHRI Randa', 'Cont docteur 9,5 HTD', 9),
(68, 'ABDELGHANI Maher', 'Maître de Conférences', 5),
(69, 'KHOUAJA Anis', 'Maître de Conférences', 5),
(70, 'HLEL Dalel', 'Maître Assistant', 3),
(71, 'ROUATBI Asma', 'Maître Assistant', 2),
(72, 'ROUIS Moeiz', 'Maître Assistant', 0),
(73, 'JDAY Rim', 'Maître Assistant', 2),
(74, 'HAMDI Belgacem', 'Professeur 5,5 HC', 10),
(75, 'JAKHLOUTI Taieb', 'Maître Assistant', 7),
(76, 'ZARROUK Elyes', 'Maître Assistant', 2),
(77, 'SAIDANE Mhamed', 'Maître Assistant', 5),
(78, 'GUERFEL Mohamed', 'Maître Assistant', 6),
(79, 'GARRAB Hatem', 'Maître de Conférences', 5),
(80, 'AMMAR Ahlem', NULL, 0),
(81, 'BOUKADIDA Hatem', 'Maître Assistant', 6),
(82, 'JAOUADI Ines', 'Maître Assistant', 2),
(83, 'HAMROUNI Fakher', 'Maître Assistant', 4),
(84, 'KRIBI Badreddine', 'Maître Assistant', 2),
(85, 'RADHOUEN Amina', 'Maître Assistant', 2),
(86, 'ZOUAOUI Safa', 'Cont docteur 9,5 HTD', 6),
(87, 'FETOUI Mourad', 'Assistant', 2),
(88, 'SAYAHI Ikbel', 'Maître Assistant', 7),
(89, 'ZRIBI Temim', 'Maître Assistant', 9),
(90, 'MALLEK Hanen', 'Maître Assistant', 4),
(91, 'HICHRI Heithem', 'Maître Assistant', 3),
(92, 'ALKAM EL Foued', NULL, 0),
(93, 'TAAMALLAH Aroua', 'Cont docteur 9,5 HTD', 10),
(94, 'BEN SALEM Manel', 'Cont docteur 9,5 HTD', 7),
(95, 'MECHI Rachid', 'Maître Assistant', 1),
(96, 'BEN AICHA Anissa', 'Maître Assistant', 5),
(97, 'BEN SALAH Chokri', 'Professeur 4,32 HC', 2),
(98, 'BAROUNI Yosra', 'Maître Assistant', 2),
(99, 'MATHLOUTHI Houda', 'Maître Assistant', 4),
(100, 'CHAABANE Haykel', 'Maître Assistant', 7),
(101, 'EL MILI Manel', 'Maître Assistant', 6),
(102, 'ATOUANI Noureddine', 'Maître Assistant', 2),
(103, 'BOUALLEGUE Kais', 'Professeur 4,32 HC', 5),
(104, 'BEN SALAH Tarek', 'Maître de Conférences', 5),
(105, 'ZBIDI JAMEL Wafa', 'Maître Assistant', 4),
(106, 'HADDAD Omar', 'Cont docteur 9,5 HTD', 7),
(107, 'BCHIR Mounira', 'Cont docteur 9,5 HTD', 10),
(108, 'AYDI Maha', 'Cont docteur 9,5 HTD', 4),
(109, 'ZOUAGHI Abderrazak', 'Maître Assistant', 5),
(110, 'BEN ABDELGHANI Farouk', 'Maître Assistant', 2),
(111, 'BANAWAZ Marwa', 'Cont docteur 9,5 HTD', 7),
(112, 'JALLALI Faycal', 'Maître Assistant', 5),
(113, 'SABRI Houssem', 'Maître Assistant', 2),
(114, 'WALI Wafa', 'Maître Assistant', 4),
(115, 'BEN SLIMANE Ichrak', 'Assistant', 3),
(116, 'CHEMKHA Hichem', 'Maître Assistant', 4),
(117, 'WALHAZI Hajer', 'PES Capes', 9),
(118, 'BRAHIM Taoufik', 'Maître Assistant', 4),
(119, 'BEN NJIMA Chayma', 'Cont docteur 9,5 HTD', 5),
(120, 'SOUISSI Werda Imen', 'Maître de Conférences 4,91 HC', 4),
(121, 'MAZGAR Akram', 'Maître Assistant', 0),
(122, 'GHOZZI Rim', 'Cont docteur 9,5 HTD', 2),
(123, 'AMMAR Anis', 'Cont docteur 9,5 HTD', 6),
(124, 'NAIJA Ahmed', 'Maître Assistant', 7),
(125, 'OMMEZINE Anis', NULL, 0),
(126, 'BEN ABDELJELIL Dorra', 'Cont docteur 9,5 HTD', 7),
(127, 'FEKI Nabih', 'Maître de Conférences', 0),
(128, 'MECHRI HoucemEddine', 'Maître Assistant', 0),
(129, 'ZAIDI Ezzine', 'Ass / Vac', 0),
(130, 'ZOUAGHI Anis', 'Maître Assistant', 7),
(131, 'BOUHAJEB Houcine', 'Cont docteur 9,5 HTD', 2),
(132, 'GUESMI Hattab', 'Maître Assistant', 6),
(133, 'DENDEN Mohsen', 'Maître Assistant', 8),
(134, 'FRIJA Mounir', 'Maître Assistant', 4),
(135, 'HOUIDI Ajmi', 'Maître de Conférences', 2),
(136, 'BEN SGHAIER Rabii', 'Maître de Conférences', 4),
(137, 'BELHADJ MESSOUD Najib', 'Maître Assistant', 5),
(138, 'ABROUG Anis', 'Maitre Technologue', 10),
(139, 'GARNA Tarek', 'Professeur 5,5 HC', 7),
(140, 'HAJJAJI Mohamed Ali', 'Maître de Conférences', 2),
(141, 'LAAMOURI Adnene', NULL, 0),
(142, 'JMOUR Marwen', 'Ass / Vac', 0),
(143, 'BEN KHALIFA Khaled', 'Maître de Conférences', 3),
(144, 'CHOUCHENE Fraj', 'Maître de Conférences', 4),
(145, 'BOUSRIH Ines', 'Ass / Vac', 0),
(146, 'MILED Mariem', NULL, 0),
(147, 'KHELIFA Nour ElHouda', 'Maître Assistant', 6),
(148, 'DHIFLAOUI Hafedh', 'Maître Assistant', 7),
(149, 'GASSAB Sirine', 'Ass / Vac', 0),
(150, 'BRINI Saoussen', 'Maître Assistant', 4),
(151, 'GHABI Chakib', 'Maître Assistant', 4),
(152, 'ZOUARI Wiem', 'Cont docteur 9,5 HTD', 10),
(153, 'MEMMI Hanene', 'Assistant', 2),
(154, 'ABDALLAH Bouthaina', 'Maître Assistant  8,14 HTD', 5),
(155, 'CHIBANI Radhia', 'Maître Assistant', 7),
(156, 'GAFSI Mohamed', 'Maître Assistant', 8),
(157, 'HAMOUDA Mahmoud', 'Maître de Conférences', 2),
(158, 'TRABELSI Ramzi', 'Maître Assistant', 0),
(159, 'MAZZOUZ Souha', 'Maître Assistant', 2),
(160, 'BAWEB BHOURI Ines', 'Maître Assistant', 4),
(161, 'REGAIG Ines', 'Cont doctorant 6 HTD', 6),
(162, 'KHEDHER Atef', 'Maître de Conférences', 6),
(163, 'KHALIL Makram', 'Maître Assistant', 5),
(164, 'KORTAS Salem', 'Assistant', 9),
(165, 'CHAIEB Salwa', 'Ass / Vac', 0),
(166, 'BEN ABID Nabiha', 'Cont docteur 9,5 HTD', 5),
(167, 'BEN FREDJ Hana', 'Cont docteur 9,5 HTD', 6),
(168, 'BLEL Nesrine', NULL, 0),
(169, 'BEN AHMED Ikram', 'Cont docteur 9,5 HTD', 7),
(170, 'BEN AHMED Sofiene', 'PP Emérité- Capes14  H TD', 12),
(171, 'GAIED Refka', 'Ass / Vac', 0),
(172, 'MDALLA Mohamed', 'Ass / Vac', 0),
(173, 'BOUDEN Mondher', 'Maître Assistant', 8),
(174, 'HASSINE Hela', 'PP Emérite Détaché  14  H TD', 10),
(175, 'TOUNSI Mohamed', 'Maître Assistant', 5),
(176, 'CHOUAIEB Olfa', 'Maître Assistant', 6),
(177, 'KHALIFA Taher', NULL, 0),
(178, 'BDIRI GABBOUJ Houda', 'Maître Assistant', 5),
(179, 'BAHRIA Nihed', 'Maître Assistant', 6),
(180, 'TRIMECH GHDIRA Elhem', 'PP Emérite CE-Détache', 12),
(181, 'TERRES Mohamed Ali', 'Professeur 5,5 HC', 5),
(182, 'GHOURABI Yosra Maha', 'PP Emérité- Capes14  H TD', 10),
(183, 'BOUDOKHANE Imene', 'PP Emérité- Capes14  H TD', 14),
(184, 'SAADANI Asma', 'Ass / Vac', 0),
(185, 'MALKI Wahid', 'PP Emérité- Capes14  H TD', 12),
(186, 'BOUTOUB Ahmed', 'Maître Assistant', 4),
(187, 'EL FAYEDH Hassen', 'Maître de Conférences', 6),
(188, 'BEN ALI Mounir', 'Maître Assistant', 5),
(189, 'RZOUGUA Lamia', 'Maître Assistant', 11),
(190, 'OUNI Jalel', 'Prof. Agrégé Principal Emérite12H', 10),
(191, 'DHOUKAR Aida', 'PP Emérité- Capes14  H TD', 11),
(192, 'EL GHARBI Ramzi', 'PP Emérité- Capes14  H TD', 10),
(193, 'BADRI Ilhem', 'PP Emérite CE', 12),
(194, 'CHATTI Sami', 'Professeur 5,5 HC', 0),
(195, 'MAHFOUDHI Alkamel', NULL, 0),
(196, 'MTIBAA Riadh', 'Maître Assistant', 5),
(197, 'KHEMAJA Maha', 'Maître de Conférences', 2),
(198, 'KHLIFI Mouadh', 'Maître de Conférences', 5),
(199, 'DARDOUR Houda', 'Maître Assistant', 4),
(200, 'JABLA Roua', 'Cont docteur 9,5 HTD', 4),
(201, 'BEN FADHEL Yosra', NULL, 0),
(202, 'Procédes de mise en forme par déformation plastique', NULL, 0),
(203, 'LAZREG Maher', 'Maître Assistant', 5),
(204, 'ABOUDA Wadii', NULL, 0),
(205, 'BAHLOUL Riadh', 'Maître de Conférences', 8),
(206, 'ACHOUR Sami', 'Maître Assistant', 0),
(207, 'ALKAMEL Foued', 'Ass / Vac', 0),
(208, 'TAGORTI Mohamed Ali', 'Professeur 5,5 HC', 8),
(209, 'HFAIEDH Anoir', NULL, 0),
(210, 'HADIJI Hajer', 'Maître Assistant 7,13HTD', 4),
(211, 'ZAAFRANE Yosr', NULL, 0),
(212, 'ISO 14001', NULL, 0),
(213, 'BELHAJ MOHAMED Mbarka', 'Cont docteur 9,5 HTD', 7),
(214, 'GUEDRI Lamia', 'Maître Assistant', 4),
(215, 'ATTIAOUI Walid', 'Assistant', 5),
(216, 'KHEMILI Imed', NULL, 0),
(217, 'YOUSSEF Khaoula', NULL, 0),
(218, 'MESSAOUDI Seifeddine', NULL, 0),
(219, 'MAKNI Hajer', 'Maître Assistant 7,13HTD', 10),
(220, 'SAGAAMA Insaf', 'Maître Assistant', 7),
(221, 'BEN AMOR A', 'PP Emérite CE', 9),
(222, 'SASSI Imen', NULL, 0),
(223, 'TAKTAK Wissem', 'Maître Assistant 8,48 HTD', 7),
(224, 'BELGACEM Selma', 'Maître Assistant', 7),
(225, 'KORTAS Nawal', 'Cont docteur 9,5 HTD', 8),
(226, 'KANZARI Dalel', 'Maître Assistant', 5),
(227, 'YOUSSFI Amani', NULL, 0),
(228, 'ARFAOUI Latifa', 'Cont docteur 9,5 HTD', 4),
(229, 'BRAHEM Maryem', 'Cont docteur 9,5 HTD', 6),
(230, 'HADJ KACEM Mouna', 'Cont docteur 9,5 HTD', 4),
(231, 'MECHHRI HoucemEddine', NULL, 0),
(232, 'TRIKI GARGOUI Dorra', 'Maître Assistant', 9);

--
-- Indexes for dumped tables
--

--
-- Indexes for table `proffer`
--
ALTER TABLE `proffer`
  ADD PRIMARY KEY (`id_proffer`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `proffer`
--
ALTER TABLE `proffer`
  MODIFY `id_proffer` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=233;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
